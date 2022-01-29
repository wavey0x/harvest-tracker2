import logging
import time, os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from itertools import count
from brownie import chain, interface, web3, Contract, ZERO_ADDRESS
from web3._utils.events import construct_event_topic_set
from yearn.utils import closest_block_after_timestamp, contract_creation_block
from yearn.prices import magic, constants
from yearn.db.models import Reports, Transactions, Event, Session, engine, select
from sqlalchemy import select as Select, desc, asc
# from yearn.utils import closest_block_after_timestamp, get_block_timestamp
from yearn.networks import Network
from yearn.events import create_filter, decode_logs
# from yearn.yearn import Yearn
import warnings
warnings.filterwarnings("ignore", ".*Class SelectOfScalar will not make use of SQL compilation caching.*")
warnings.filterwarnings("ignore", ".*It has been discarded*")
logger = logging.getLogger("yearn.historical_tvl")


CHAIN_VALUES = {
    Network.Mainnet: {
        "START_DATE": datetime(2020, 2, 12, tzinfo=timezone.utc),
        "START_BLOCK": 11772924,
        "REGISTRY_ADDRESS": "0x50c1a2eA0a861A967D9d0FFE2AE4012c2E053804",
        "REGISTRY_HELPER_ADDRESS": "0x52CbF68959e082565e7fd4bBb23D9Ccfb8C8C057",
        "LENS_ADDRESS": "0x5b4F3BE554a88Bd0f8d8769B9260be865ba03B4a",
        "LENS_DEPLOY_BLOCK": 12707450,
        "VAULT_ADDRESS030": "0x5f18C75AbDAe578b483E5F43f12a39cF75b973a9",
        "VAULT_ADDRESS031": "0xdA816459F1AB5631232FE5e97a05BBBb94970c95",
        "KEEPER_CALL_CONTRACT": "0x5f18C75AbDAe578b483E5F43f12a39cF75b973a9",
        "KEEPER_TOKEN": "0x5f18C75AbDAe578b483E5F43f12a39cF75b973a9",
        "YEARN_TREASURY": "0x93A62dA5a14C80f265DAbC077fCEE437B1a0Efde",
    },
    Network.Fantom: {
        "START_DATE": datetime(2021, 4, 30, tzinfo=timezone.utc),
        "START_BLOCK": 16241109,
        "REGISTRY_ADDRESS": "0x727fe1759430df13655ddb0731dE0D0FDE929b04",
        "REGISTRY_HELPER_ADDRESS": "0x8CC45f739104b3Bdb98BFfFaF2423cC0f817ccc1",
        "REGISTRY_HELPER_DEPLOY_BLOCK": 18456459,
        "LENS_ADDRESS": "0x97D0bE2a72fc4Db90eD9Dbc2Ea7F03B4968f6938",
        "LENS_DEPLOY_BLOCK": 18842673,
        "VAULT_ADDRESS030": "0x637eC617c86D24E421328e6CAEa1d92114892439",
        "VAULT_ADDRESS031": "0x637eC617c86D24E421328e6CAEa1d92114892439",
        "KEEPER_CALL_CONTRACT": "0x39cAcdb557CA1C4a6555E00203B4a00B1c1a94f8",
        "KEEPER_TOKEN": "",
        "YEARN_TREASURY": "0x89716Ad7EDC3be3B35695789C475F3e7A3Deb12a",
    },
    Network.Arbitrum: {
        "START_DATE": datetime(2021, 9, 14, tzinfo=timezone.utc),
        "START_BLOCK": 4841854,
        "REGISTRY_ADDRESS": "",
        "REGISTRY_HELPER_ADDRESS": "",
        "LENS_ADDRESS": "",
        "VAULT_ADDRESS030": "",
        "VAULT_ADDRESS031": "",
        "KEEPER_CALL_CONTRACT": "",
        "KEEPER_TOKEN": "",
        "YEARN_TREASURY": "",
    }
}


# Primary vault interface
vault = interface.IVault032(CHAIN_VALUES[chain.id]["VAULT_ADDRESS031"])
vault = web3.eth.contract(str(vault), abi=vault.abi)
topics = construct_event_topic_set(
    vault.events.StrategyReported().abi, web3.codec, {}
)
# Deprecated vault interface
if chain.id == 1:
    vault_v030 = interface.IVault030(CHAIN_VALUES[chain.id]["VAULT_ADDRESS030"])
    vault_v030 = web3.eth.contract(vault_address_v030, abi=vault_v030.abi)
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
    event_filter = web3.eth.filter({'topics': topics, "fromBlock": last_reported_block + 1})
    if chain.id == 1:
        event_filter_v030 = web3.eth.filter({'topics': topics_v030, "fromBlock": last_reported_block030 + 1})
    
    while True: # Keep this as a long-running script
        events_to_process = []
        transaction_hashes = []

        for strategy_report_event in decode_logs(event_filter.get_new_entries()):
            e = Event(False, strategy_report_event, strategy_report_event.transaction_hash.hex())
            handle_event(e.event, e.multi_harvest, e.isOldApi)
            
        if chain.id == 1: # No old vaults deployed anywhere other than mainnet
            for strategy_report_event in decode_logs(event_filter_v030.get_new_entries()):
                e = Event(True, strategy_report_event, strategy_report_event.transaction_hash.hex())
                handle_event(e.event, e.multi_harvest, e.isOldApi)

        time.sleep(interval_seconds)
        
        """
        # The code below is used to populate the "multi_harvest" property #
        for strategy_report_event in decode_logs(event_filter.get_new_entries()):
            e = Event(False, strategy_report_event, strategy_report_event.transaction_hash.hex())
            if e.txn_hash in transaction_hashes:
                e.multi_harvest = True
                for i in range(0, len(events_to_process)):
                        if e.txn_hash == events_to_process[i].txn_hash:
                            events_to_process[i].multi_harvest = True
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
                else:
                    transaction_hashes.append(strategy_report_event.transaction_hash.hex())
                events_to_process.append(e)

        for e in events_to_process:
            handle_event(e.event, e.multi_harvest, e.isOldApi)
        time.sleep(interval_seconds)
        """

def handle_event(event, multi_harvest, isOldApi):
    txn_hash = event.transaction_hash.hex()
    tx = web3.eth.getTransactionReceipt(txn_hash)
    gas_price = web3.eth.getTransaction(txn_hash).gasPrice
    # TODO: Detect if endorsed ✅ # Could use review
    # TODO: Lookup last harvest ✅
    # TODO: Lookup last harvest on chain id for each abi type ✅
    # TODO: Block duplicates on insert ✅
    # TODO: Refactor to two tables: Transactions + Reports ✅
    # TODO: Add keep3r payment logic ✅
    # TODO: Add logger
    # TODO: Make it multichain compatible (better varible lookups)
    # TODO: Add APY figures
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
    
    txn_record_exists = transaction_record_exists(txn_hash)
    if not transaction_record_exists(txn_hash):
        t = Transactions()
        t.chain_id = chain.id
        t.txn_hash = txn_hash
        t.block = event.block_number
        t.txn_to = tx.to
        t.txn_from = tx["from"]
        t.txn_gas_used = tx.gasUsed
        t.txn_gas_price = gas_price
        t.eth_price_at_block = magic.get_price(constants.weth, t.block)
        t.call_cost_eth = gas_price * tx.gasUsed / 1e18
        t.call_cost_usd = t.eth_price_at_block * t.call_cost_eth
        if chain.id == 1:
            t.kp3r_price_at_block = magic.get_price("0x1cEB5cB57C4D4E2b2433641b95Dd330A33185A44", t.block)
            t.kp3r_paid = get_keeper_payment(tx)
            t.kp3r_paid_usd = t.kp3r_paid * t.kp3r_price_at_block / 1e18
            t.keeper_called = t.kp3r_paid > 0
        if chain.id == 250:
            if t.txn_to == "0x39cAcdb557CA1C4a6555E00203B4a00B1c1a94f8":
                t.keeper_called = True
            else:
                t.keeper_called = False
        t.date = datetime.utcfromtimestamp(ts)
        t.date_string = dt
        t.timestamp = ts
        t.updated_timestamp = datetime.now()

    r.vault_address = event.address
    r.block = event.block_number
    r.txn_hash = txn_hash
    strategy = interface.IStrategy043(r.strategy_address)
    vault = interface.IVault032(r.vault_address)

    r.gov_fee_in_want, r.strategist_fee_in_want = parse_fees(tx, r.vault_address, r.strategy_address)
    r.gain_post_fees = r.gain - r.loss - r.strategist_fee_in_want - r.gov_fee_in_want
    r.want_token = strategy.want()
    r.want_price_at_block = magic.get_price(r.want_token, r.block)
    
    r.vault_api = vault.apiVersion()
    r.vault_decimals = vault.decimals()
    r.want_gain_usd = r.gain / 10**r.vault_decimals * r.want_price_at_block
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
        if not txn_record_exists:
            session.add(t)
        session.commit()
        print(f"added report for strategy {r.strategy_address} at txn hash {r.txn_hash}")

def transaction_record_exists(txn_hash):
    with Session(engine) as session:
        query = select(Transactions).where(
            Transactions.txn_hash == txn_hash
        )
        result = session.exec(query).first()
        if result == None:
            return False
        return True

def last_harvest_block():
    with Session(engine) as session:
        query = select(Reports.block).where(
            Reports.chain_id == chain.id, Reports.vault_api != "0.3.0"
        ).order_by(desc(Reports.block))
        result1 = session.exec(query).first()
        if result1 == None:
            result1 = CHAIN_VALUES[chain.id]["START_BLOCK"]
        if chain.id == 1:
            query = select(Reports.block).where(
                Reports.chain_id == chain.id, Reports.vault_api == "0.3.0"
            ).order_by(desc(Reports.block))
            result2 = session.exec(query).first()
            if result2 == None:
                result2 = CHAIN_VALUES[chain.id]["START_BLOCK"]
        else:
            result2 = 0
            
    return result1, result2

def get_keeper_payment(tx):
    kp3r_token = "0x1cEB5cB57C4D4E2b2433641b95Dd330A33185A44"
    token = interface.IERC20(kp3r_token)
    token = web3.eth.contract(str(kp3r_token), abi=token.abi)
    decoded_events = token.events.Transfer().processReceipt(tx)
    amount = 0
    for e in decoded_events:
        if e.address == kp3r_token:
            sender, receiver, token_amount = e.args.values()
            if receiver == tx["from"]:
                amount = token_amount
    return amount

def query():
    txn_hash = "0x360bb1c46b9434b97043cae49eeea67c0948069eb1c1466f12ecb2ddda336e66"
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

def parse_fees(tx, vault_address, strategy_address):
    treasury = CHAIN_VALUES[chain.id]["YEARN_TREASURY"]
    token = interface.IVault032(vault_address)
    token = web3.eth.contract(str(vault_address), abi=token.abi)
    decoded_events = token.events.Transfer().processReceipt(tx)
    amount = 0
    gov_fee_in_underlying = 0
    strategist_fee_in_underlying = 0
    counter = 0
    #   Using this var, we will keep an counter to ensure sequence of events 
    #   follows the vault fee transfer sequence: 
    #   1. mint
    #   2. transfer to strategy
    #   3. transfer to treasury
    for e in decoded_events:
        if e.address == vault_address:
            sender, receiver, token_amount = e.args.values()
            if sender == ZERO_ADDRESS:
                counter = 1
                continue
            if receiver == strategy_address and counter == 1:
                counter = 2
                strategist_fee_in_underlying = (
                    token_amount * (
                        interface.IVault032(vault_address).pricePerShare(block_identifier=tx.blockNumber) /
                        10 ** interface.IVault032(vault_address).decimals()
                    )
                )
                continue
            elif counter == 1:
                counter = 0
            if receiver == treasury and counter == 2:
                counter = 0
                gov_fee_in_underlying = (
                    token_amount * (
                        interface.IVault032(vault_address).pricePerShare(block_identifier=tx.blockNumber) /
                        10 ** interface.IVault032(vault_address).decimals()
                    )
                )
                continue
            elif counter == 1 or counter == 2:
                counter = 0
    return gov_fee_in_underlying, strategist_fee_in_underlying
            

def check_endorsed(strategy_address, block):
    lens = interface.ILens(CHAIN_VALUES[chain.id]["LENS_ADDRESS"])
    deploy_block = contract_creation_block(strategy_address)
    if deploy_block > CHAIN_VALUES[chain.id]["LENS_DEPLOY_BLOCK"]:
        # If deployed after lens, we can use lens to lookup
        prod_strats = list(lens.assetsStrategiesAddresses.call(block_identifier=block))
        if strategy_address in prod_strats:
            return True
        else:
            return False
    else:
        # Must lookup using alternate logic.
        # Here we can make the assumption that if at time of harvest, vault.rewards() != Treasury, it is not endorsed
        # Further, let's use registry helper's list of endorsed vaults to match against.
        try:
            vault_address = interface.IStrategy043(strategy_address).vault()
            if interface.IVault032(vault_address).rewards(block_identifier=block) != CHAIN_VALUES[chain.id]["YEARN_TREASURY"]:
                return False
            registry_helper = interface.IRegistryHelper(CHAIN_VALUES[chain.id]["REGISTRY_HELPER_ADDRESS"])
            vaults = registry_helper.getVaults()
            if vault_address in vaults:
                return True
            else:
                return False
        except:
            return False