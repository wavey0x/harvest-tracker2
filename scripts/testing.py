import logging
import time, os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from itertools import count
from brownie import chain, interface, web3, Contract
from web3._utils.events import construct_event_topic_set
from yearn.utils import closest_block_after_timestamp, contract_creation_block
from yearn.prices import magic
from yearn.db.models import Reports, Event, Session, engine, select
from sqlalchemy import select as Select, desc, asc
# from yearn.utils import closest_block_after_timestamp, get_block_timestamp
from yearn.networks import Network
from yearn.events import create_filter, decode_logs
# from yearn.yearn import Yearn
import warnings
warnings.filterwarnings("ignore", ".*Class SelectOfScalar will not make use of SQL compilation caching.*")

logger = logging.getLogger("yearn.historical_tvl")

START_DATE = {
    Network.Mainnet: datetime(2020, 2, 12, tzinfo=timezone.utc),  # first iearn deployment
    Network.Fantom: datetime(2021, 4, 30, tzinfo=timezone.utc),  # ftm vault deployment 2021-09-02
    Network.Arbitrum: datetime(2021, 9, 14, tzinfo=timezone.utc),  # ironbank deployemnt
}

START_BLOCK = {
    Network.Mainnet: 11772924,
    Network.Fantom: 16241109,
    Network.Arbitrum: 4841854,
}

REGISTRY_ADDRESS = {
    Network.Mainnet: "0x50c1a2eA0a861A967D9d0FFE2AE4012c2E053804",
    Network.Fantom: "0x50c1a2eA0a861A967D9d0FFE2AE4012c2E053804",
    Network.Arbitrum: "0x50c1a2eA0a861A967D9d0FFE2AE4012c2E053804",
}

REGISTRY_HELPER_ADDRESS = {
    Network.Mainnet: "0x52CbF68959e082565e7fd4bBb23D9Ccfb8C8C057", 
    Network.Fantom: "0x52CbF68959e082565e7fd4bBb23D9Ccfb8C8C057",  
    Network.Arbitrum: "0x52CbF68959e082565e7fd4bBb23D9Ccfb8C8C057",
}

LENS_ADDRESS = {
    Network.Mainnet: "0x5b4F3BE554a88Bd0f8d8769B9260be865ba03B4a",
    Network.Fantom: "0x5b4F3BE554a88Bd0f8d8769B9260be865ba03B4a",
    Network.Arbitrum: "0x5b4F3BE554a88Bd0f8d8769B9260be865ba03B4a",
}



# Primary vault interface
vault_address = "0xdA816459F1AB5631232FE5e97a05BBBb94970c95"
vault = interface.IVault032(vault_address)
vault = web3.eth.contract(str(vault), abi=vault.abi)
# Deprecated vault interface
vault_address_v030 = "0x5f18C75AbDAe578b483E5F43f12a39cF75b973a9"
vault_v030 = interface.IVault030(vault_address_v030)
vault_v030 = web3.eth.contract(vault_address_v030, abi=vault_v030.abi)

topics = construct_event_topic_set(
    vault.events.StrategyReported().abi, web3.codec, {}
)
topics_v030 = construct_event_topic_set(
    vault_v030.events.StrategyReported().abi, web3.codec, {}
)

def main():
    log_loop(25)

def log_loop(interval_seconds):
    last_reported_block, last_reported_block030 = last_harvest_block()

    print("latest_block",last_reported_block)
    print("latest_block030",last_reported_block030)
    print("blocks behind (new)", chain.height - last_reported_block)
    print("blocks behind (old)", chain.height - last_reported_block030)
    event_filter_v030 = web3.eth.filter({'topics': topics_v030, "fromBlock": last_reported_block030 + 1})
    event_filter = web3.eth.filter({'topics': topics, "fromBlock": last_reported_block + 1})
    
    while True: # Keep this as a long-running script
        events_to_process = []
        transaction_hashes = []
        
        for strategy_report_event in decode_logs(event_filter.get_new_entries()):
            e = Event(False, strategy_report_event, strategy_report_event.transaction_hash.hex())
            if e.txn_hash in transaction_hashes:
                e.multi_harvest = True
                for i in range(0, len(events_to_process)):
                        if e.txn_hash == events_to_process[i].txn_hash:
                            events_to_process[i].multi_harvest = True
                            print("🥳 found match")
            else:
                transaction_hashes.append(strategy_report_event.transaction_hash.hex())
            events_to_process.append(e)
            
        if chain.id == 1: # No old vaults deployed anywhere other than mainnet
            for strategy_report_event in decode_logs(event_filter_v030.get_new_entries()):
                e = Event(True, strategy_report_event, strategy_report_event.transaction_hash.hex())
                if e.txn_hash in transaction_hashes:
                    e.multi_harvest = True
                    for i in range(0, len(events_to_process)):
                        if e.txn_hash == events_to_process[i].txn_hash:
                            events_to_process[i].multi_harvest = True
                            print("🥳 found match")
                else:
                    transaction_hashes.append(strategy_report_event.transaction_hash.hex())
                events_to_process.append(e)

        for e in events_to_process:
            handle_event(e.event, e.multi_harvest, e.isOldApi)
        time.sleep(interval_seconds)

def handle_event(event, multi_harvest, isOldApi):
    txn_hash = event.transaction_hash.hex()
    tx = web3.eth.getTransactionReceipt(txn_hash)
    # TODO: Detect if endorsed ✅
    # TODO: Lookup last harvest ✅
    # TODO: Lookup last harvest on chain id for each api type ✅
    # TODO: Block duplicates on insert ✅
    # TODO: Add logger
    ts = chain[event.block_number].timestamp
    dt = datetime.utcfromtimestamp(ts).strftime("%m/%d/%Y, %H:%M:%S")
    r = Reports()
    r.multi_harvest = multi_harvest
    r.chain_id = chain.id
    if isOldApi:
        r.strategy_address, r.gain, r.loss, r.total_gain, r.total_loss, r.total_debt, r.debt_added, r.debt_ratio = event.values()
    else:
        r.strategy_address, r.gain, r.loss, r.debt_paid, r.total_gain, r.total_loss, r.total_debt, r.debt_added, r.debt_ratio = event.values()
    if check_endorsed(r.strategy_address, event.block_number) == False:
        print("🚫 strategy not endorsed", r.strategy_address, txn_hash, event.block_number)
        return
    r.block = event.block_number
    r.txn_hash = txn_hash
    r.txn_to = tx.to
    r.txn_from = tx["from"]
    r.txn_gas_used = tx.gasUsed
    r.txn_gas_price = tx.effectiveGasPrice
    r.txn_fee_eth = tx.effectiveGasPrice * tx.gasUsed / 1e18
    price_usd = magic.get_price("0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE", r.block)
    r.txn_fee_usd = price_usd * r.txn_fee_eth

    r.vault_address = event.address

    strategy = interface.IStrategy043(r.strategy_address)
    vault = interface.IVault032(r.vault_address)
    r.want_token = strategy.want()
    r.vault_api = vault.apiVersion()
    r.vault_decimals = vault.decimals()
    r.vault_name = vault.name()
    r.strategy_name = strategy.name()
    r.strategy_api = strategy.apiVersion()
    r.vault_symbol = vault.symbol()
    r.date = datetime.utcfromtimestamp(ts)
    r.date_string = dt
    r.timestamp = ts

    with Session(engine) as session:
        query = select(Reports.id).where(
            Reports.chain_id == chain.id, Reports.strategy_address == r.strategy_address
        ).order_by(desc(Reports.block))

        report_id = session.exec(query).first()
        r.previous_report_id = report_id
        r.updated_timestamp = datetime.now()
        session.add(r)
        session.commit()
        print(f"added report for strategy {r.strategy_address} at txn hash {r.txn_hash}")

def last_harvest_block():
    with Session(engine) as session:
        query = select(Reports.block).where(
            Reports.chain_id == chain.id, Reports.vault_api != "0.3.0"
        ).order_by(desc(Reports.block))
        result1 = session.exec(query).first()
        if result1 == None:
            result1 = START_BLOCK[chain.id]
        if chain.id == 1:
            query = select(Reports.block).where(
                Reports.chain_id == chain.id, Reports.vault_api == "0.3.0"
            ).order_by(desc(Reports.block))
            result2 = session.exec(query).first()
            if result2 == None:
                result2 = START_BLOCK[chain.id]
        else:
            result2 = 0
            
    return result1, result2

def query():
    txn_hash = "0x8141d310d407e9a3583b91c3d0a003964fc6a7133268c0d58350bbfc3cca6373"
    tx = web3.eth.getTransactionReceipt(txn_hash)
    
    with Session(engine) as session:
        strategy_address = "0xB5F6747147990c4ddCeBbd0d4ef25461a967D079"
        query = select(Reports).where(
            Reports.chain_id == 1, Reports.strategy_address == strategy_address
        ).order_by(desc(Reports.block))

        query = select(Reports.id).where(
            Reports.chain_id == 1, Reports.strategy_address == strategy_address
        ).order_by(desc(Reports.block))
        result = session.exec(query).first()
        # select(Reports).order_by(Person.age)

def check_endorsed(strategy_address, block):
    lens = interface.ILens(LENS_ADDRESS[chain.id])
    deploy_block = contract_creation_block(strategy_address)
    if deploy_block > 12707450:
        # Can lookup on lens
        prod_strats = list(lens.assetsStrategiesAddresses.call(block_identifier=block))
        if strategy_address in prod_strats:
            return True
        else:
            return False
    else:
        # Must lookup the hard way.
        try:
            vault_address = interface.IStrategy043(strategy_address).vault()
            registry_helper = interface.IRegistryHelper(REGISTRY_HELPER_ADDRESS[chain.id])
            vaults = registry_helper.getVaults()
            if vault_address in vaults:
                return True
            else:
                return False
        except:
            return False