from time import timezone
from flask import Flask
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import datetime
from firebase_admin import credentials, firestore, initialize_app

app = Flask(__name__)
CORS(app)

cred = credentials.Certificate('key.json')
default_app = initialize_app(cred)
db = firestore.client(default_app)
product_ref = db.collection('products')

@app.route("/product/new/<product_name>")
def add_product(product_name):
    url = "https://www.digitec.ch/fr/s1/product/" + product_name
    page = requests.get(url)
    soup = BeautifulSoup(page.content, 'html.parser')
    #<strong class="sc-1aeovxo-1 jchvyw">449.–</strong>
    price = soup.find("strong", {"class": "sc-1aeovxo-1"}).text
    # all text in h1 with .sc-jqo5ci-0
    name = soup.find("h1", {"class": "sc-jqo5ci-0"}).text
    # remove the last 2 characters
    price = price[:-2]
    
    #get current date and time
    date = datetime.datetime.now()
    item = {
        "name": name,
        "price_history": [
            {
                "price": price,
                "date": date
            }],
        "url": url
    }
    product_ref.document(product_name).set(item)
    
    return {
        "name": name,
        "price": price,
        "date": date,
        "url": url
    }

@app.route("/product/<product_name>")
def get_product(product_name):
    doc = product_ref.document(product_name).get()
    return {
        "name": doc.to_dict()["name"],
        "price": doc.to_dict()["price_history"][-1]["price"],
        "date": doc.to_dict()["price_history"][-1]["date"],
        "url": doc.to_dict()["url"],
        "image": get_product_image(doc.to_dict()["url"])
    }

def get_product_image(url):
    print("get_product_image", url)
    page = requests.get(url)
    soup = BeautifulSoup(page.content, 'html.parser')
    # <img src="https://static.digitecgalaxus.ch/Files/1/7/7/6/0/3/1/7/UNIFI-UAP-AC-PRO--0a1e.jpg" class="sc-1ienw2c-1 ecKVWY" decoding="auto" alt="Image du produit" loading="eager">
    return soup.find("img", {"class": "sc-1ienw2c-1"})["src"]
    

@app.route("/product/<product_name>", methods=['DELETE'])
def delete_product(product_name):
    product_ref.document(product_name).delete()
    return "deleted"

@app.route("/products")
def getAllProductsWithLatestPrices():
    print("getAllProductsWithLatestPrices")
    products = product_ref.get()
    prices = []
    for product in products:
        product_last_price = update_product_price(product.to_dict()['url'])
        print("product_last_price", product_last_price.get('date'))
        prices.append({
            "name": product.to_dict()["name"],
            "price": product_last_price.get("price"),
            "date": product_last_price.get("date"),
            "url": product.to_dict()["url"]
        })
    return {"products": prices}
    

def update_product_price(url):
    print("update_product_price", url)
    page = requests.get(url)
    soup = BeautifulSoup(page.content, 'html.parser')
    #<strong class="sc-1aeovxo-1 jchvyw">449.–</strong>
    price = soup.find("strong", {"class": "sc-1aeovxo-1"}).text
    price = price[:-2]
    
    # Tue Oct 04 2022 14:16:55 GMT+0200 (heure d’été d’Europe centrale)
    date = datetime.datetime.now(tz=datetime.timezone.utc)
    
    price_history = {
        "price": price,
        "date": date
    }

    product_ref.document(url.split("/")[-1]).set({
        "price_history": firestore.ArrayUnion([
            price_history
        ])
        }, merge=True)
    
    return price_history
    
    