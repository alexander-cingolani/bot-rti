from sqlalchemy import create_engine, insert, select
from sqlalchemy.orm import sessionmaker
from sshtunnel import SSHTunnelForwarder
import models

server = SSHTunnelForwarder(
    ("192.168.0.21", 22),
    ssh_username="rti",
    ssh_password="Gx75[0pC|#G]}O[",
    remote_bind_address=("172.30.0.2", 3306),
)
server.start()
a = server.local_bind_port  # type: ignore

pg_url = f"postgresql+psycopg://<DB_USERNAME>:<DB_PASSWORD>@127.0.0.1:{a}/DB"
mysql_url = "mysql+mysqlconnector://<DB_USERNAME>:<DB_PASSWORD>@172.21.0.02:3306/DB"

pg_engine = create_engine(pg_url)
mysql_engine = create_engine(mysql_url)

pg = sessionmaker(bind=pg_engine)
mysql = sessionmaker(bind=mysql_engine)

pg_session = pg()
mysql_session = mysql()

models.Base.metadata.create_all(mysql_engine)


for table in models.Base.metadata.sorted_tables:
    src_table = models.Base.metadata.tables[table.name]
    stmt = insert(table)
    for row in pg_session.execute(select(src_table)):
        mysql_session.execute(stmt.values(row))
mysql_session.commit()
mysql_session.close()
pg_session.close()
