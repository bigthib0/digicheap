from time import timezone
from flask import Flask
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from firebase_admin import credentials, firestore, initialize_app
import smtplib, ssl

FETCH_PRICE_INTERVAL = 2  #minutes

app = Flask(__name__)
CORS(app)

cred = credentials.Certificate('key.json')
default_app = initialize_app(cred)
db = firestore.client(default_app)
product_ref = db.collection('products')

def get_price_date_digitec(product_name):
    url = "https://www.digitec.ch/fr/s1/product/" + product_name
    page = requests.get(url)
    soup = BeautifulSoup(page.content, 'html.parser')
    # <strong class="sc-1aeovxo-1 jchvyw">449.–</strong>
    price = float(soup.find("strong", {"class": "sc-1aeovxo-1"}).text)
    # all text in h1 with .sc-jqo5ci-0
    name = soup.find("h1", {"class": "sc-jqo5ci-0"}).text
    # remove the last 2 characters
    price = price[:-2]
    
    return (name, price, url)

def get_price_date_galaxus(product_name):
    url = "https://www.galaxus.ch/fr/s12/product/" + product_name
    page = requests.get(url)
    soup = BeautifulSoup(page.content, 'html.parser')
    # <span class="price">CHF 449.–</span>
    price = float(soup.find("strong", {"class": "sc-1aeovxo-1"}).text)
    # all text in h1 with .sc-jqo5ci-0
    name = soup.find("h1", {"class": "sc-jqo5ci-0"}).text
    
    return (name, price, url)

@app.route("/product/new/<product_name>")
def add_product(product_name, origin):
    url = ""
    price = 0
    name = ""
    if origin == "digitec":
        (name, price, url) = get_price_date_digitec()
    if origin == "galaxus":
        (name, price,url) = get_price_date_galaxus()

    # get current date and time
    date = datetime.datetime.now()
    item = {
        "name": name,
        "price_history": [
            {
                "price": price,
                "date": date
            }],
        "url": url,
        "image": get_product_image(url)
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
        "image": doc.to_dict()["image"]
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


@app.route("/product/<product_name>/history")
def get_product_history(product_name):
    doc = product_ref.document(product_name).get()
    return doc.to_dict()["price_history"]


@app.route("/products")
def getAllProductsWithLatestPrices():
    print("getAllProductsWithLatestPrices")
    products = product_ref.get()
    prices = []
    for product in products:
        prices.append({
            "name": product.to_dict()["name"],
            "price": product.to_dict()["price_history"][-1]["price"],
            "date": product.to_dict()["price_history"][-1]["date"],
            "url": product.to_dict()["url"],
            "image": product.to_dict()["image"]
        })
    return {"products": prices}


@app.route("/products/update")
def updateAllProducts():
    print("updateAllProducts")
    products = product_ref.get()
    for product in products:
        update_product(product.to_dict()['url'])
    return "updated"


def update_product(url):
    print("update_product_price", url)
    page = requests.get(url)
    soup = BeautifulSoup(page.content, 'html.parser')
    # <strong class="sc-1aeovxo-1 jchvyw">449.–</strong>
    price = soup.find("strong", {"class": "sc-1aeovxo-1"}).text
    price = price[:-2]

    # Tue Oct 04 2022 14:16:55 GMT+0200 (heure d’été d’Europe centrale)
    date = datetime.datetime.now(tz=datetime.timezone.utc)

    price_history = {
        "price": price,
        "date": date
    }

    image = soup.find("img", {"class": "sc-1ienw2c-1"})["src"]

    product_ref.document(url.split("/")[-1]).set({
        "price_history": firestore.ArrayUnion([
            price_history
        ]),
        "image": image
    }, merge=True)

    return price_history


@app.route('/')
def index():
    return "<h1>Welcome to our server !!</h1>"

sched = BackgroundScheduler(daemon = True)
sched.add_job(updateAllProducts, 'interval', minutes = FETCH_PRICE_INTERVAL)
sched.start()

def send_email(dest, message):
    server.sendmail("price-alert@digiless.ch", dest, message)

port = 465  # For SSL
password = "webklmkW#4"

# Create a secure SSL context
context = ssl.create_default_context()

message = """\
Subject: Hi there

This message is sent from Python."""

with smtplib.SMTP_SSL("mail.infomaniak.com", port, context=context) as server:
    server.login("price-alert@digiless.ch", password)
    send_email("thibaut-michaud@hotmail.ch", message)                                                                        

if __name__ == '__main__':
    # Threaded option to enable multiple instances for multiple user access support
    app.run(threaded=True, port=5000)
