from flask import Flask, jsonify

app = Flask(__name__)

items = [
    {
        'id': 1,
        'title': 'Hammer',
        'description': 'This is a hammer'
    },
    {
        'id': 2,
        'title': 'Basketball',
        'description': 'This is a basketball',
    }
]


@app.route('/api/v1.0/all/items', methods=['GET'])
def get_tasks():
    return jsonify({'items': items})


if __name__ == '__main__':
    app.run(debug=True)
