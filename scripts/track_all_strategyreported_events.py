import asyncio, json, time, psycopg2
from collections import defaultdict
from datetime import datetime
from brownie import chain, web3, Contract, interface
from rich import print
from rich.progress import track
from rich.table import Table
from web3._utils.events import construct_event_topic_set
# from yearn.prices import magic
from yearn.utils import contract # Something about this import ignores repeated events
from brownie.exceptions import ContractNotFound

import warnings
warnings.simplefilter('ignore')

vault_address = "0xdA816459F1AB5631232FE5e97a05BBBb94970c95"
vault = interface.IVault032(vault_address)
vault = web3.eth.contract(str(vault), abi=vault.abi)

vault_address_v030 = "0x5f18C75AbDAe578b483E5F43f12a39cF75b973a9"
vault_v030 = interface.IVault030(vault_address_v030)
vault_v030 = web3.eth.contract(vault_address_v030, abi=vault_v030.abi)

topics = construct_event_topic_set(
    vault.events.StrategyReported().abi, 
    web3.codec, 
    {
    }
)
topics_v030 = construct_event_topic_set(
    vault_v030.events.StrategyReported().abi, 
    web3.codec, 
    {
    }
)

list_of_prod_vaults = []
list_of_prod_strats = []
vault_deploy_block = 13181454

def main():
    ts = time.time()
    dt = datetime.utcfromtimestamp(ts).strftime("%m/%d/%Y, %H:%M:%S")
    print("starting STRAEGYREPORTED...",dt)

    
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            asyncio.gather(
                log_loop(2) # run every 2 seconds
            )
        ) 
    finally:
        # close loop to free up system resources
        loop.close()


async def log_loop(poll_interval):
    last_reported_block = last_report_block()
    last_reported_block030 = last_report_block030()
    print("latest_block",last_reported_block)
    print("latest_block030",last_reported_block030)
    print("blocks behind (new)", chain.height - last_reported_block)
    print("blocks behind (old)", chain.height - last_reported_block030)
    event_filter_v030 = web3.eth.filter({'topics': topics_v030, "fromBlock": last_reported_block030})
    event_filter = web3.eth.filter({'topics': topics, "fromBlock": last_reported_block})
    
    while True: # Keep this as a long-running script
        for report in event_filter.get_new_entries():
            handle_event(report)
        for report in event_filter_v030.get_new_entries():
            handle_event(report)
        
        await asyncio.sleep(poll_interval)

    # define function to handle events and print to the console
def handle_event(event):
    tx_hash = event.transactionHash.hex()
    tx = web3.eth.getTransactionReceipt(tx_hash)
    version = interface.IVault032(event.address).apiVersion()
    if version == "0.3.0":
        decoded_events = vault_v030.events.StrategyReported({}).processReceipt(tx)
    else:
        decoded_events = vault.events.StrategyReported({}).processReceipt(tx)
    list_of_prod_strats, list_of_prod_vaults = populate_current_assets()
    for e in decoded_events:
        if e.address not in list_of_prod_vaults:
            print("🚫 not a prod vault")
            continue
        ts = chain[e.blockNumber].timestamp
        dt = datetime.utcfromtimestamp(ts).strftime("%m/%d/%Y, %H:%M:%S")
        r = Report()
        
        if version == "0.3.0":
            r.strategy_address, r.gain, r.loss, r.totalGain, r.totalLoss, r.totalDebt, r.debtAdded, r.debtRatio = e.args.values()
            r.debtPaid = 0
        else:
            r.strategy_address, r.gain, r.loss, r.debtPaid, r.totalGain, r.totalLoss, r.totalDebt, r.debtAdded, r.debtRatio = e.args.values()
        if r.strategy_address not in list_of_prod_strats:
            print("🚫 not a prod strat",r.strategy_address)
            r = Report()
            continue
        
        r.chain_id = chain.id
        r.block = e.blockNumber
        r.txn_to = tx.to
        r.txn_from = tx["from"]
        r.tx_hash = tx_hash
        r.vault_address = e.address
        strategy = interface.IStrategy043(r.strategy_address)
        v = interface.IVault032(e.address)
        r.vault_token = v.token()
        r.vault_symbol = v.symbol()
        r.vault_api = v.apiVersion()
        r.strategy_name = strategy.name()
        r.date_string = dt
        r.timestamp = ts
        write_report_to_db(r)

def populate_current_assets():
    if chain.id == 1:
        lens = Contract("0x5b4F3BE554a88Bd0f8d8769B9260be865ba03B4a")
        registry_helper = Contract("0x52cbf68959e082565e7fd4bbb23d9ccfb8c8c057")
    return lens.assetsStrategiesAddresses(), registry_helper.getVaults()

class Report:
    gain = 0
    loss = 0
    debtPaid = 0
    totalGain = 0
    totalLoss = 0
    totalDebt = 0

def write_report_to_db(r):
    conn = None
    sql = """INSERT INTO reports (
        chain_id, 
        block, 
        txn_to, 
        txn_from,
        tx_hash,
        vault_address,
        vault_token,
        vault_symbol,
        vault_api,
        strategy_address,
        strategy_name,
        date_string,
        timestamp,
        gain,
        loss,
        debtPaid,
        totalGain,
        totalLoss,
        totalDebt,
        debtAdded,
        debtRatio
        )
        VALUES(
            %s, 
            %s, 
            %s, 
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        )"""

    record_to_insert = (
        r.chain_id, 
        r.block, 
        str(r.txn_to), 
        str(r.txn_from),
        str(r.tx_hash),
        str(r.vault_address),
        str(r.vault_token),
        str(r.vault_symbol),
        str(r.vault_api),
        str(r.strategy_address),
        str(r.strategy_name),
        str(r.date_string),
        r.timestamp,
        r.gain,
        r.loss,
        r.debtPaid,
        r.totalGain,
        r.totalLoss,
        r.totalDebt,
        r.debtAdded,
        r.debtRatio
    )
    try:
        conn = psycopg2.connect("host=192.168.1.102 port=5432 dbname=harvests connect_timeout=10 user=postgres password=pass")
        # create a new cursor
        cur = conn.cursor()
        # execute the INSERT statement
        cur.execute(sql, record_to_insert)
        conn.commit()
        send_notifications(r)
        # get the generated id back
        # commit the changes to the database
        conn.commit()
        # close communication with the database
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()

def last_report_block():
    sql = """SELECT MAX(block) FROM reports;"""
    try:
        conn = psycopg2.connect("host=192.168.1.102 port=5432 dbname=harvests connect_timeout=10 user=postgres password=pass")
        # create a new cursor
        cur = conn.cursor()
        # execute the INSERT statement
        cur.execute(sql)
        conn.commit()
        # get the generated id back
        try:
            latest_block = cur.fetchone()[0]
        except:
            latest_block = chain.height
        # commit the changes to the database
        conn.commit()
        # close communication with the database
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        return 13181454
    finally:
        if conn is not None:
            conn.close()
            return latest_block

def last_report_block030():
    sql = """SELECT MAX(block) FROM reports WHERE vault_api = '0.3.0';"""
    try:
        conn = psycopg2.connect("host=192.168.1.102 port=5432 dbname=harvests connect_timeout=10 user=postgres password=pass")
        # create a new cursor
        cur = conn.cursor()
        # execute the INSERT statement
        cur.execute(sql)
        conn.commit()
        # get the generated id back
        print("💻")
        try:
            latest_block = cur.fetchone()[0]
            if latest_block == None:
                latest_block = vault_deploy_block
        except:
            latest_block = chain.height
        # commit the changes to the database
        conn.commit()
        # close communication with the database
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        return 13181454
    finally:
        if conn is not None:
            conn.close()
            return latest_block

def send_notifications(r):
    print(r.vault_symbol + " - " + r.strategy_name)
    print("Profit 💰",r.gain)
    print("Loss 📉",r.loss)
    print("Transaction Hash",r.tx_hash)
    print("🗓️ time", r.date_string)
    print("🔗 block",r.block)
    print("To",r.txn_to)
    print()