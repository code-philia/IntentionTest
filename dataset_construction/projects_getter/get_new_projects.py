import requests
import json
import re
import csv
import time
import pandas as pd

username = '' # Fill in with your github username
token = '' # Fill in with your github token

query_constructor = lambda page, date_start, date_end : f"https://api.github.com/search/repositories?q=language:Java%20created:{date_start}..{date_end}&sort=stars&order=desc&per_page=50&page={page}"

# read from urls_old.csv
old_urls = pd.read_csv("urls_old.csv", header=None)
old_urls_set = set(old_urls[0])

url_set = set()
count = 0

for year in range(2014, 2024):
    for month in range(1, 13):
        query = ""

        if month == 12:
            query = query_constructor(1, f"{year}-{month:02d}-01", f"{year+1}-01-01")
        else:
            query = query_constructor(1, f"{year}-{month:02d}-01", f"{year}-{month+1:02d}-01")

        print(query)

        response = requests.get(query, auth=(username, token))
        data = response.json()

        while 'items' not in data:
            time.sleep(10)
            response = requests.get(query, auth=(username, token))
            data = response.json()

        for item in data['items']:
            html_url = item['html_url']
            if html_url not in old_urls_set:
                url_set.add(html_url)
                count = len(url_set)

        print(f"Year {year}, Month {month} done")
        print(f"Total: {count}")

        time.sleep(2)

print(count)

cw = csv.writer(open("urls.csv",'w'))
for url in url_set:
    cw.writerow([url])