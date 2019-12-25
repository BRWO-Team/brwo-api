from flask import Flask, jsonify, request
import firebase_admin
from firebase_admin import credentials, firestore
import google.cloud
import requests


# activate venv - brwo-venv\Scripts\activate

app = Flask(__name__)

# FIREBASE
# Use the application default credentials
cred = credentials.Certificate("./ServiceAccountKey.json")
firebase_app = firebase_admin.initialize_app(cred)
store = firestore.client()


# ROUTES
@app.route('/', methods=['GET'])
def index():
    return "You're home"


@app.route('/api/v1.0/all/items', methods=['GET'])
def get_all_items():
    items = []

    doc_ref = store.collection(u'items')  # .limit(2)

    try:
        docs = doc_ref.get()
        for doc in docs:
            items.append(doc.to_dict())
    except google.cloud.exceptions.NotFound:
        print(u'Missing data')

    return jsonify({'items': items})


@app.route('/api/v1.0/geocode', methods=['GET'])
def geocode():
    lat = request.args.get('lat')
    lon = request.args.get('lon')

    url = 'https://geocoding.geo.census.gov/geocoder/geographies/coordinates?benchmark=Public_AR_Current&vintage=Current_Current&format=json&layers=2&y={}&x={}'.format(
        lat, lon)

    r = requests.get(url)
    data = r.json()

    zip_code = data['result']['geographies']['2010 Census ZIP Code Tabulation Areas'][0]['GEOID']
    return zip_code


if __name__ == '__main__':
    # test
    #app.run(debug=True)

    # production
    app.run(debug=False, port=8080)
