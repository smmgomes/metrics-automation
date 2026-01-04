import os

from flask import Flask, jsonify

import sheets as sh

app = Flask(__name__)
@app.route("/run-etl", methods=['POST'])
def run_etl():
    try:
        sh.batch_update()
        return jsonify({"status": "success", "message": "Script executed successfully"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/clear-sheet", methods=['POST'])
def clear_sheet():
    try:
        sh.clear_all()
        return jsonify({"status": "success", "message": "Script executed successfully"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)