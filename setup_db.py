import asyncio, json, time, psycopg2
import warnings
warnings.simplefilter('ignore')


def main():
    sql = """
    CREATE TABLE reports (
        id                  SERIAL PRIMARY KEY, 
        chain_id            integer, 
        block               integer, 

        txn_hash            varchar(100),
        txn_to              varchar(100),
        txn_from            varchar(100),
        txn_gas_used        varchar(100),
        txn_gas_price       varchar(100),
        txn_fee_usd             decimal,
        txn_fee_eth             decimal,
        
        vault_address       varchar(100),
        strategy_address    varchar(100),
        gain                varchar(100),
        loss                varchar(100),
        debt_paid           varchar(100),
        total_gain          varchar(100),
        total_loss          varchar(100),
        total_debt          varchar(100),
        debt_added          varchar(100),
        debt_ratio          varchar(100),

        want_token          varchar(100),
        vault_api           varchar(100),
        vault_symbol        varchar(100),
        vault_name          varchar(100),
        vault_decimals      integer,
        strategy_name       varchar(100),
        strategy_api        varchar(100),
        previous_report_id  integer,
        
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
        cur.execute(sql2)
        conn.commit()
        cur.close()

    except:
        print(error)
    finally:
        if conn is not None:
            conn.close()

main()