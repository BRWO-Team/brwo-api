from flask import Flask, jsonify, request, url_for
import firebase_admin
from firebase_admin import credentials, firestore
import google.cloud
import requests
from geopy import distance


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


@app.route('/api/v1.0/count/items', methods=['GET'])
def get_count_items():
    return str(len(list(store.collection('items').get())))


# @app.route('/api/v1.0/all/items', methods=['GET'])
# def get_all_items():
#     items = []

#     doc_ref = store.collection(u'items')  # .limit(2)

#     try:
#         docs = doc_ref.get()
#         for doc in docs:
#             items.append(doc.to_dict())
#     except google.cloud.exceptions.NotFound:
#         print(u'Missing data')

#     return jsonify({'items': items})


@app.route('/api/v1.0/lazy/most_recent/items', methods=['GET'])
def get_most_recent_items_lazy():
    n = int(request.args.get('n'))
    page = int(request.args.get('page'))
    limit = n * page
    items = []
    doc_ref = store.collection(u'items').order_by(
        u'date_time_added', direction=firestore.Query.DESCENDING).limit(limit)
    max_len = sum(1 for _ in store.collection(u'items').order_by(
        u'date_time_added', direction=firestore.Query.DESCENDING).get()
    )
    if limit > max_len:
        if limit - max_len < n:
            try:
                docs = doc_ref.get()
                for doc in docs:
                    items.append(doc.to_dict())
            except google.cloud.exceptions.NotFound:
                print(u'Missing data')

            print('Partial return: ' + str(-(n - (limit - max_len))))
            return jsonify({'items': items[-(n - (limit - max_len)):], 'no_more_results': True})
        else:
            print('No return')
            return jsonify({'items': [], 'no_more_results': True})
    else:
        try:
            docs = doc_ref.get()
            for doc in docs:
                items.append(doc.to_dict())
                # items.append(doc.id)
        except google.cloud.exceptions.NotFound:
            print(u'Missing data')

        print('Normal return: ' + str(-n))
        return jsonify({'items': items[-n:], 'no_more_results': False})


@app.route('/api/v1.0/most_recent/items', methods=['GET'])
def get_most_recent_items():
    items = []
    n = int(request.args.get('n'))

    doc_ref = store.collection(u'items').order_by(
        u'date_time_added', direction=firestore.Query.DESCENDING).limit(n)

    try:
        docs = doc_ref.get()
        for doc in docs:
            items.append(doc.to_dict())
            # items.append(doc.id)
    except google.cloud.exceptions.NotFound:
        print(u'Missing data')

    return jsonify({'items': items})


@app.route('/api/v1.0/n/items', methods=['GET'])
def get_n_items():
    items = []
    n = int(request.args.get('n'))

    doc_ref = store.collection(u'items').limit(n)

    try:
        docs = doc_ref.get()
        for doc in docs:
            # doc.id
            items.append(doc.to_dict())
    except google.cloud.exceptions.NotFound:
        print(u'Missing data')

    return jsonify({'items': items})


@app.route('/api/v1.0/distance/items', methods=['GET'])
def get_distance_items():
    items = []
    lat = float(request.args.get('lat'))
    lon = float(request.args.get('lon'))
    dist = request.args.get('distance_mi')

    location = (lat, lon)

    doc_ref = store.collection(u'items')
    try:
        docs = doc_ref.get()
        for doc in docs:
            coords = (doc.to_dict()['lat'], doc.to_dict()['lon'])

            if round(distance.distance(location, coords).miles, 2) <= float(dist):
                items.append(doc.to_dict())
    except google.cloud.exceptions.NotFound:
        print(u'Missing data')

    return jsonify({'items': items})


@app.route('/api/v1.0/user/items', methods=['GET'])
def get_users_items():
    items = []
    uid = int(request.args.get('userid'))

    doc_ref = store.collection(u'items').where(u'userid', u'==', uid).order_by(
        u'date_time_added', direction=firestore.Query.DESCENDING)

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


def has_no_empty_params(rule):
    defaults = rule.defaults if rule.defaults is not None else ()
    arguments = rule.arguments if rule.arguments is not None else ()
    return len(defaults) >= len(arguments)


@app.route('/api/v1.0/items/categories', methods=['GET'])
def get_categories_items():
    categories = []

    doc_ref = store.collection(u'items')

    try:
        docs = doc_ref.get()
        for doc in docs:
            for cat in doc.to_dict()['categories']:
                if cat not in categories:
                    categories.append(cat)
    except google.cloud.exceptions.NotFound:
        print(u'Missing data')

    return jsonify({'categories': sorted(categories)})


@app.route("/site-map")
def site_map():
    links = []
    for rule in app.url_map.iter_rules():
        # Filter out rules we can't navigate to in a browser
        # and rules that require parameters
        if "GET" in rule.methods and has_no_empty_params(rule):
            url = url_for(rule.endpoint, **(rule.defaults or {}))
            links.append((url, rule.endpoint))
    return dict(links)


@app.route('/api/v1.0/items/postnew', methods=['POST'])
def new_item_post():
    data = request.get_json()
    print(data)
    store.collection(u'items').add(data)
    res = {'status': 'ok'}
    return jsonify(res)


if __name__ == '__main__':
    # test
    # app.run(debug=True)

    # production
    app.run(debug=False, port=8080)
