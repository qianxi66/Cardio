import time

import IPython
import pandas as pd
import requests


host = "http://127.0.0.1:5002"
# user_id = "amzn1.ask.account.AMAUHCXHP5MDPU5NLIJ5RHL4B34PTBWUQSSGBUAK2RASAITVGFUI3BAZLBNAXCE6PYH7GLGDJF5NASF7XGM3QRZK3YGXOB5RBDUP5W2ZWGSBFQ5HSCFO7PSVKF5SKM4RGDYIBCOHPCOBDWHF6XUJ2OFBVCXSJECSDC7NTUQWKK3SCM52XCIIXOPSGHN4XV6GLWD3XQCOOQJFOKO6PRYYRHAV3DZJD7NBTRENFR5R3M"

content = {
    "content": "this is a debug message. imagine user said something, and write your reply."
}

times = []
for i in range(1, 11):
    user_id = i
    api_url = f"{host}/alexa_user/{user_id}/conversation"
    for j in range(10):
        start_time = time.time()
        resp = requests.post(
            api_url,
            json=content,
            headers={"Authorization": "Bearer G53Lbl5/c2X+00kESxWnkcF"},
        )
        end_time = time.time()
        times.append(end_time - start_time)
        print(resp.json())
        time.sleep(2)

print(times)
df = pd.DataFrame(times)
df.to_parquet("openai.parquet")
IPython.embed()
