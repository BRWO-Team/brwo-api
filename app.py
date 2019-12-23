from flask import Flask, jsonify
import firebase_admin
import google.cloud
from firebase_admin import credentials, firestore

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


if __name__ == '__main__':
    app.run(debug=True)
