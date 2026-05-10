from gmind import db


def test_init_db(database_url):
    db.init_db(database_url)
