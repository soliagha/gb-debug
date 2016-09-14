
from bookshelf import get_model, storage
from flask import Blueprint, current_app, redirect, render_template, request, \
    url_for

import time
import os
import urllib2
import csv
from gcloud import storage as gstorage
from gcloud import bigquery
from gcloud.bigquery import SchemaField
from googleapiclient import discovery
from oauth2client.client import GoogleCredentials

crud = Blueprint('crud', __name__)


def _get_storage_client():
    return gstorage.Client(
        project=current_app.config['PROJECT_ID'])


@crud.route('/<id>/upload_csv', methods=['GET', 'POST'])
def upload_csv(id):

    report = get_model().read(id)
    csvResponse = ''

    SCHEMA = [
        SchemaField('organizationName_ext', 'STRING', mode='required'),
        SchemaField('organizationName_int', 'STRING', mode='required'),
        SchemaField('organizationID', 'INTEGER', mode='required'),
        SchemaField('amountOver', 'INTEGER', mode='required'),
        SchemaField('amountUnder', 'INTEGER', mode='required'),
        SchemaField('label', 'STRING', mode='required'),
        SchemaField('giftType', 'STRING', mode='required'),
        SchemaField('donorType', 'STRING', mode='required'),
        SchemaField('date', 'STRING', mode='required'),
    ]

    client = bigquery.Client(current_app.config['PROJECT_ID'])
    dataset = client.dataset('Gift')
    # dataset.create()  # API request

    table = dataset.table(id, SCHEMA)

    if request.method == 'POST':
        csvFile = request.files.get('csv')

        if table.exists():
            table.delete()
            table.create()
        else:
            table.create()

        # Save file to cloud via blob
        public_url = storage.upload_file(
           csvFile.read(),
           csvFile.filename,
           csvFile.content_type)

        response = urllib2.urlopen(public_url)
        table.upload_from_file(response, source_format='CSV', skip_leading_rows=1)
        data = report
        data['csvUrl'] = public_url

        get_model().update(data, id)
        report = get_model().read(id)
        csvResponse = 'The CSV was for report ' + report['reportName'] + ' was successfully added to Greasebelt. ' + \
                      'Please click here to request a sync with Fundtracker.'

    return view_csv(id)


@crud.route('/<id>/view_csv', methods=['GET', 'POST'])
def view_csv(id):

    report = get_model().read(id)

    if not report['csvUrl']:
        upload_csv(id)

    else:
        credentials = GoogleCredentials.get_application_default()
        service = discovery.build('bigquery', 'v2', credentials=credentials)
        projectId = current_app.config['PROJECT_ID']
        datasetId = 'Gift'
        tableId = id

        bq_request = service.tabledata().list(projectId=projectId, datasetId=datasetId, tableId=tableId)
        data = bq_request.execute()

        rowCollection = []
        headerRow = []

        # __file__ refers to the file settings.py
        APP_ROOT = os.path.dirname(os.path.abspath(__file__))   # refers to application_top
        APP_CSV = os.path.join(APP_ROOT, 'csv/placeholder.csv')

        # csvFile = file('/csv/test.csv')
        csvFile = open(APP_CSV, 'w+')
        a = csv.writer(csvFile)

        for row in data['rows']:
            rowVal = []
            for cell in row['f']:
                rowVal.append(cell['v'])
            rowCollection.append(rowVal)

        headerRow.append(['organizationName_ext', 'organizationName_int', 'organizationID', 'amountOver', 'amountUnder', 'label', 'giftType', 'donorType', 'date'])
        a.writerows(headerRow)
        a.writerows(rowCollection)

        # Save file to cloud via blob
        public_url = storage.upload_file(
            csvFile.read(),
            report['reportName'] + '.csv',
            'text/csv')

        csvFile.close()
        csvRender = rowCollection

        csvResponse = ''

    return render_template("csv.html", report=report, csvResponse=csvResponse, csvRender=csvRender, public_url=public_url)

# [START upload_image_file]
def upload_report_file(file, id):
    """
    Upload the user-uploaded file to Google Cloud Storage and retrieve its
    publicly-accessible URL.
    """
    if not file:
        return None

    public_url = storage.upload_file(
        file.read(),
        file.filename,
        file.content_type,
        id
    )

    reportFile = (public_url, file.filename)

    current_app.logger.info(
        "Uploaded file %s as %s.", file.filename, public_url)

    return reportFile
# [END upload_image_file]


@crud.route("/", methods=['GET', 'POST'])
def list():
    token = request.args.get('page_token', None)
    if token:
        token = token.encode('utf-8')

    search = []

    if request.method == 'POST':
        search = request.form.to_dict(flat=True)

    reports, next_page_token = get_model().list(
        cursor=token, search=search)

    return render_template(
        "list.html",
        reports=reports,
        next_page_token=next_page_token,
        search=search)


@crud.route('/<id>')
def view(id):
    report = get_model().read(id)
    return render_template("view.html", report=report)


@crud.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':

        data = request.form.to_dict(flat=True)
        report = get_model().create(data)

        if request.files.get('image'):
            try:
                reportFile = upload_report_file(request.files.get('image'), report['id'])
                data['reportUrl'] = reportFile[0]
                data['reportName'] = reportFile[1]

            except:
                print ('Report file upload failed!')

            get_model().update(data, report['id'])

        return redirect(url_for('.view', id=report['id']))

    return render_template("form.html", action="Add", report={})


@crud.route('/<id>/edit', methods=['GET', 'POST'])
def edit(id):
    report = get_model().read(id)

    if request.method == 'POST':
        data = request.form.to_dict(flat=True)
        reportFile = upload_report_file(request.files.get('image'), id)

        if reportFile:
            data['reportUrl'] = reportFile[0]
            data['reportName'] = reportFile[1]

        report = get_model().update(data, id)

        return redirect(url_for('.view', id=report['id']))

    return render_template("form.html", action="Edit", report=report)


@crud.route('/<id>/delete')
def delete(id):

    report = get_model().read(id)

    try:  # Delete CSV data
        client = bigquery.Client(current_app.config['PROJECT_ID'])
        dataset = client.dataset('Gift')
        dataset.table(id).delete()
    except:
        print ('Deleting CSV failed for report: ' + id)
        print ('It is possible there is no report file associated to this report record.')

    try:  # Delete report blob
        storage.delete_file(report['reportUrl'])
    except :
        print ('Deleting report blob failed for report ID ' + id)

    try:  # Delete Greasebelt report
        get_model().delete(id)
    except:
        print ('Deleting Greasebelt report failed for report ID ' + id)

    return redirect(url_for('.list'))
