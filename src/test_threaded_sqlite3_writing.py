import sqlite3
import threading
import pandas as pd
import random
import tqdm
import time
import queue

def main():
    dbpath = "test.db"

    def generate_data(q: queue.Queue, thread_id):
        print(f"Thread {thread_id} started")
        ITERATIONS = 100
        for i in tqdm.tqdm(range(ITERATIONS), desc=f"Thread {thread_id}"):
            df = pd.DataFrame.from_dict({"id":[i + ITERATIONS*thread_id]})
            q.put(df)
            
                
    def write_data(q: queue.Queue, db_path, threads):
        print("Writer thread started")
        con = sqlite3.connect(db_path)
        i = 0
        while True:
            try:
                df = q.get(block=False, timeout=None)
                df.to_sql(con=con, name="table_pass_conn", if_exists='append', index=False)
                i += 1
                if i % 100 == 0:
                    print(f"Written {i} rows")
            except queue.Empty as e:
                # check if other theads are alive
                time.sleep(0.1)
                if not any([t.is_alive() for t in threads]):
                    break
            except Exception as e:
                print(e)
        con.close()
        print("End of writer thread")

    #queue
    q = queue.Queue()

    genrator_threads_num = 10
    generator_threads = []
    for i in range(genrator_threads_num):
        t = threading.Thread(target=generate_data, args=(q, i))
        generator_threads.append(t)
        
    writer_thread = threading.Thread(target=write_data, args=(q, dbpath, generator_threads))
        
    for t in generator_threads:
        t.start()
    writer_thread.start()
        
    for t in generator_threads:
        t.join()
    writer_thread.join()
        
        
    conn = sqlite3.connect(dbpath)
    result = conn.cursor().execute("SELECT COUNT(*) FROM table_pass_conn").fetchall()
    print("Number of rows in the table: ", result)

    conn.close()


main()