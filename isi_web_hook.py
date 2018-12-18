#!/usr/bin/env python
from flask import Flask, request
import json
import os
app = Flask(__name__)

FILE_ENCODING = 'iso-8859-15'

@app.route("/cloud/job-file/size/", methods=['POST'])
def filesize():
    payload = json.loads(request.data)
    files = payload['files']
    files_with_size = []
    for f in files:
        try:
            statinfo = os.stat(f['name'])
            file_size = statinfo.st_size
        except:
            file_size = 0;
        files_with_size.append({'name':f['name'],'size':0})

    return json.dumps({'files':files_with_size})

if __name__ == '__main__':
   app.run(host='0.0.0.0')
