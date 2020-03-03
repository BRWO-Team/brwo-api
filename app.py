from flask import Flask, jsonify, request, url_for
from flask_cors import CORS, cross_origin
import firebase_admin
from firebase_admin import credentials, firestore
import google.cloud
import requests
import os
import shutil
import time
import json
from geopy import distance
import datetime
from fuzzywuzzy import fuzz
from flask_swagger_ui import get_swaggerui_blueprint


DEV = False
PORT = 8080
# PORT = 5000
URL_BASE = '/api/v1.0'

# activate venv - brwo-venv\Scripts\activate

app = Flask(__name__)
CORS(app)

### swagger specific ###
SWAGGER_URL = '/swagger'
API_URL = '/static/swagger.json'
SWAGGERUI_BLUEPRINT = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "BRWO_API"
    }
)
app.register_blueprint(SWAGGERUI_BLUEPRINT, url_prefix=SWAGGER_URL)
### end swagger specific ###


# FIREBASE
# Use the application default credentials
cred = credentials.Certificate("./ServiceAccountKey.json")
firebase_app = firebase_admin.initialize_app(cred)
store = firestore.client()


def add_ids():
    """adds document ids to document body"""
    for doc in store.collection(u'items').get():
        doc_id = doc.id
        item = store.collection(u'items').document(doc_id)
        item.update({u'item_id': doc_id})


#ROUTES##################################################################################
@app.route('/', methods=['GET'])
def index():
    return "You're home"


def has_no_empty_params(rule):
    defaults = rule.defaults if rule.defaults is not None else ()
    arguments = rule.arguments if rule.arguments is not None else ()
    return len(defaults) >= len(arguments)


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


##GET####################################################################################

###ITEMS#################################################################################
@app.route(URL_BASE + '/items/count', methods=['GET'])
def get_count_items():
    return str(len(list(store.collection('items').get())))


@app.route(URL_BASE + '/items/most_recent', methods=['GET'])
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


@app.route(URL_BASE + '/items/most_recent_lazy', methods=['GET'])
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


@app.route(URL_BASE + '/items/n', methods=['GET'])
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


@app.route(URL_BASE + '/items/fuzzy_search', methods=['GET'])
def get_fuzzy_items():
    items = []
    query = request.args.get('query')

    doc_ref = store.collection(u'items')

    try:
        docs = doc_ref.get()
        for doc in docs:
            match_ratio = fuzz.partial_ratio(query, doc.to_dict()['title'])
            if match_ratio > 70:
                data = doc.to_dict()
                # data = {}
                # data['title'] = doc.to_dict()['title']
                data['match_ratio'] = match_ratio
                items.append(data)
    except google.cloud.exceptions.NotFound:
        print(u'Missing data')

    sorted_items = sorted(items, key=lambda k: k['match_ratio'], reverse=True)
    return jsonify({'items': sorted_items})


@app.route(URL_BASE + '/items/distance', methods=['GET'])
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
            if 'lat' in doc.to_dict().keys() and 'lon' in doc.to_dict().keys():
                coords = (doc.to_dict()['lat'], doc.to_dict()['lon'])

                if round(distance.distance(location, coords).miles, 2) <= float(dist):
                    items.append(doc.to_dict())
    except google.cloud.exceptions.NotFound:
        print(u'Missing data')

    return jsonify({'items': items})


@app.route(URL_BASE + '/item', methods=['GET'])
def get_item_by_id():
    item_id = request.args.get('item_id')

    doc_ref = store.collection(u'items').where(u'item_id', u'==', item_id)

    try:
        # count = sum(1 for _ in doc_ref.get())
        item = next(doc_ref.get()).to_dict()
    except google.cloud.exceptions.NotFound:
        print(u'Missing data')
        return {'status': 'error'}
    except StopIteration:
        print(u'No items with that id')
        return {'status': 'error', 'error_message': "No item with that id"}

    return jsonify({'status': 'ok', 'item': item})


@app.route(URL_BASE + '/items/category', methods=['GET'])
def get_item_by_category():
    items = []
    category = request.args.get('category')

    doc_ref = store.collection(u'items').where(
        u'categories', u'array_contains', category)

    try:
        docs = doc_ref.get()
        for doc in docs:
            items.append(doc.to_dict())
    except google.cloud.exceptions.NotFound:
        print(u'Missing data')
        return {'status': 'error'}

    return jsonify({'status': 'ok', 'items': items})


@app.route(URL_BASE + '/items/user', methods=['GET'])
def get_users_items():
    items = []
    uid = int(request.args.get('uid'))

    doc_ref = store.collection(u'items').where(u'userid', u'==', uid).order_by(
        u'date_time_added', direction=firestore.Query.DESCENDING)

    try:
        docs = doc_ref.get()
        for doc in docs:
            items.append(doc.to_dict())
    except google.cloud.exceptions.NotFound:
        print(u'Missing data')

    return jsonify({'items': items})


###USERS#################################################################################
@app.route(URL_BASE + '/users/getinfo', methods=['GET'])
def get_users_info():
    uid = request.args.get('uid')
    doc_ref = store.collection(u'users').where(u'uid', u'==', uid)
    try:
        info = [i.to_dict() for i in doc_ref.get()]
        if len(info) == 1:
            return jsonify({'user_info': info[0]})
        elif len(info) < 1:
            return jsonify({'error': 'No user found with that id'})
        elif len(info) > 1:
            return jsonify({'error': 'Multiple users found with this id, there is an issue with the data'})
    except google.cloud.exceptions.NotFound:
        return jsonify({'error': 'Error encountered'})


###CATEGORIES############################################################################
@app.route(URL_BASE + '/categories', methods=['GET'])
def get_categories_items():
    categories = []

    doc_ref = store.collection(u'items')

    try:
        docs = doc_ref.get()
        for doc in docs:
            if "categories" in doc.to_dict():
                for cat in doc.to_dict()['categories']:
                    if cat not in categories:
                        categories.append(cat)
    except google.cloud.exceptions.NotFound:
        print(u'Missing data')

    return jsonify({'categories': sorted(categories)})


###GEOCODE###############################################################################
@app.route(URL_BASE + '/geocode', methods=['GET'])
def geocode():
    lat = request.args.get('lat')
    lon = request.args.get('lon')

    url = 'https://geocoding.geo.census.gov/geocoder/geographies/coordinates?benchmark=Public_AR_Current&vintage=Current_Current&format=json&layers=2&y={}&x={}'.format(
        lat, lon)

    r = requests.get(url)
    data = r.json()

    zip_code = data['result']['geographies']['2010 Census ZIP Code Tabulation Areas'][0]['GEOID']
    return zip_code


##POST###################################################################################

###ITEMS#################################################################################
@app.route(URL_BASE + '/items', methods=['POST'])
def new_item_post():
    try:
        os.mkdir('image')
    except:
        pass

    data = json.loads(request.form['data'])
    data['images'] = []
    data['date_time_added'] = datetime.datetime.now()

    for i in request.files:
        image = request.files[i]

        image.save(os.path.join('image', image.filename))

        url = "https://api.imgur.com/3/upload"
        payload = {'type': 'file'}
        with open('image/' + image.filename, 'rb') as image_file:
            files = [
                ('image', image_file)
            ]
            headers = {
                'Authorization': 'Client-ID cbd7000560fd3b7',
                'Authorization': 'Bearer 4b570172640f7938523c0f58d3e74ecccd729e76'
            }
            response = requests.request(
                "POST", url, headers=headers, data=payload, files=files)

            link = response.json()['data']['link']

        data['images'].append(link)

        time.sleep(1)
    try:
        shutil.rmtree('image')
    except:
        pass
    try:
        # print(data)
        # store.collection(u'items').add(data)

        new_city_ref = store.collection(u'items').document()
        data['item_id'] = new_city_ref.id
        new_city_ref.set(data)
        res = {'status': 'ok', 'data': data}
        if data is None:
            raise Exception
    except:
        res = {'status': 'error'}
    return jsonify(res)

###USERS#################################################################################
@app.route(URL_BASE + '/users/update', methods=['POST'])
def user_update():
    try:
        data = request.get_json()
        id = data['uid']
        user_ids = set([i.id for i in store.collection(u'users').get()])
        if id in user_ids:
            ref = store.collection(u'users').document(id)
            ref.update(data)
        else:
            store.collection(u'users').document(id).set(data)
        res = {'status': 'ok', 'user_data': data}
    except Exception as e:
        print(e)
        res = {'status': 'error'}
    return jsonify(res)


##DEPRECATED#############################################################################

# @app.route(URL_BASE + '/all/items', methods=['GET'])
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


# @app.route(URL_BASE + '/items/submitimage', methods=['POST'])
# def submit_image():
#     image = request.files.get('image', '')

#     image.save(os.path.join('image', image.filename))

#     url = "https://api.imgur.com/3/upload"
#     payload = {'type': 'file'}
#     with open('image/' + image.filename, 'rb') as image_file:
#         files = [
#             ('image', image_file)
#         ]
#         headers = {
#             'Authorization': 'Client-ID cbd7000560fd3b7',
#             'Authorization': 'Bearer 4b570172640f7938523c0f58d3e74ecccd729e76'
#         }
#         response = requests.request(
#             "POST", url, headers=headers, data=payload, files=files)

#         link = response.json()['data']['link']

#     time.sleep(1)
#     shutil.rmtree('image')
#     os.mkdir('image')
#     return jsonify({'status': 'ok', 'url': link})


if __name__ == '__main__':
    app.run(debug=DEV, port=PORT)

    # test
    # app.run(debug=True)

    # production
    # app.run(debug=False, port=8080)
