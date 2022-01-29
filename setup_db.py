import asyncio, json, time, psycopg2
import warnings
warnings.simplefilter('ignore')


def main():
    sql_create_reports = """
    CREATE TABLE reports (
        id                  SERIAL PRIMARY KEY, 

        chain_id            integer, 
        block               bigint, 
        txn_hash            varchar(150) NOT NULL,

        vault_address       varchar(100),
        strategy_address    varchar(100),
        gain                numeric(78,0),
        loss                numeric(78,0),
        debt_paid           numeric(78,0),
        total_gain          numeric(78,0),
        total_loss          numeric(78,0),
        total_debt          numeric(78,0),
        debt_added          numeric(78,0),
        debt_ratio          integer,

        want_token          varchar(100),
        want_price_at_block decimal,
        want_gain_usd       decimal,
        gov_fee_in_want         numeric(78,0),
        strategist_fee_in_want  numeric(78,0),
        gain_post_fees      numeric(78,0),
        vault_api           varchar(100),
        vault_symbol        varchar(100),
        vault_name          varchar(100),
        vault_decimals      bigint,
        strategy_name       varchar(100),
        strategy_api        varchar(100),
        previous_report_id  integer,
        multi_harvest       boolean,
        
        date                date,
        date_string         varchar(100),
        timestamp           bigint,
        updated_timestamp   date DEFAULT now()
    );"""

    sql_create_transactions = """
    CREATE TABLE transactions (
        txn_hash            varchar(150) PRIMARY KEY,
        chain_id            integer, 
        block               bigint, 
        txn_to              varchar(100),
        txn_from            varchar(100),

        txn_gas_used        numeric(78,0),
        txn_gas_price       numeric(78,0),
        eth_price_at_block  decimal,
        call_cost_usd       decimal,
        call_cost_eth       decimal,
        kp3r_paid           numeric(78,0),
        kp3r_price_at_block decimal,
        kp3r_paid_usd       decimal,
        keeper_called       boolean,

        date                date,
        date_string         varchar(100),
        timestamp           bigint,
        updated_timestamp   date DEFAULT now()
    );"""

    sql_add_unique_constraint = """
    ALTER TABLE reports ADD CONSTRAINT unique_records UNIQUE 
    (txn_hash, block, vault_address, strategy_address, gain, loss, debt_added, debt_ratio);
    """
    try: 
        # read database configuration
        # params = config()
        # connect to the PostgreSQL database
        conn = psycopg2.connect("host=192.168.1.102 port=5432 dbname=reports connect_timeout=10 user=postgres password=pass")
        # create a new cursor
        cur = conn.cursor()
        cur.execute(sql_create_reports)
        cur.execute(sql_create_transactions)
        # cur.execute(sql2)
        conn.commit()
        cur.close()

    except:
        print(error)
    finally:
        if conn is not None:
            conn.close()

# Used this query to manually set multi-harvest value
sql = """
UPDATE reports
SET multi_harvest=TRUE
WHERE txn_hash IN(
	SELECT txn_hash
	FROM reports
	WHERE txn_hash IN (
	    SELECT txn_hash
	    FROM reports
	    GROUP BY txn_hash
	    HAVING COUNT(id) > 1
	)
)
"""
main()