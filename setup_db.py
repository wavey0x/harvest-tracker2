import asyncio, json, time, psycopg2
import warnings
warnings.simplefilter('ignore')


def main():
    sql = """
    CREATE TABLE reports2 (
        id                  SERIAL PRIMARY KEY, 
        chain_id            integer, 
        block               integer, 

        txn_hash            varchar(100),
        txn_to              varchar(100),
        txn_from            varchar(100),
        txn_gas_used        numeric(78,0),
        txn_gas_price       numeric(78,0),
        txn_fee_usd             decimal,
        txn_fee_eth             decimal,
        
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
        vault_api           varchar(100),
        vault_symbol        varchar(100),
        vault_name          varchar(100),
        vault_decimals      integer,
        strategy_name       varchar(100),
        strategy_api        varchar(100),
        previous_report_id  integer,
        multi_harvest       boolean,
        
        date                date,
        date_string         varchar(100),
        timestamp           integer,
        updated_timestamp   date DEFAULT now()
    );"""

    sql2 = """
    ALTER TABLE reports ADD CONSTRAINT unique_records UNIQUE 
    (txn_hash, block, vault_address, strategy_address, gain, loss, debt_added, debt_ratio);
    """
    try: 
        # read database configuration
        # params = config()
        # connect to the PostgreSQL database
        conn = psycopg2.connect("host=192.168.1.102 port=5432 dbname=harvests connect_timeout=10 user=postgres password=pass")
        # create a new cursor
        cur = conn.cursor()
        print(sql)
        cur.execute(sql)
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