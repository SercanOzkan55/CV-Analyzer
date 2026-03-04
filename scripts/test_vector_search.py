from dotenv import load_dotenv
import os
from sqlalchemy import create_engine, text


def make_vec_string(val, dim=1536):
    return '[' + ','.join([str(val)] * dim) + ']'


def main():
    load_dotenv()
    url = os.getenv('DATABASE_URL')
    if not url:
        print('NO_DATABASE_URL')
        return 2
    url = url.replace('postgresql+psycopg2://', 'postgresql://', 1)
    engine = create_engine(url)
    with engine.connect() as conn:
        # insert two candidates
        v1 = make_vec_string(0.01)
        v2 = make_vec_string(0.02)
        try:
            # Insert using literal vector representation (safe for test data)
            conn.execute(text(f"INSERT INTO candidates (cv_text, cv_embedding) VALUES ('cand1', '{v1}'::vector)"))
            conn.execute(text(f"INSERT INTO candidates (cv_text, cv_embedding) VALUES ('cand2', '{v2}'::vector)"))
            conn.commit()
        except Exception as e:
            print('INSERT_ERROR', e)

        # query similarity to a job vector similar to cand1
        q = make_vec_string(0.0105)
        try:
            res = conn.execute(text(f"SELECT id, cv_text, (cv_embedding <#> '{q}'::vector) AS score FROM candidates WHERE cv_embedding IS NOT NULL ORDER BY score LIMIT 5")).fetchall()
            print('SEARCH_RESULTS:')
            for row in res:
                print(row)
        except Exception as e:
            print('SEARCH_ERROR', e)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
