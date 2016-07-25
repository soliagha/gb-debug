
from bookshelf import get_model, storage
from flask import Blueprint, current_app, redirect, render_template, request, \
    url_for

import time
import urllib2
import csv
from gcloud import storage as soliagha
from gcloud import bigquery
from gcloud.bigquery import SchemaField
from googleapiclient import discovery
from oauth2client.client import GoogleCredentials

crud = Blueprint('crud', __name__)


def _get_storage_client():
    return soliagha.Client(
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
        #SchemaField('csvUrl', 'STRING', mode='required'),
    ]

    if request.method == 'POST':

        csvFile = request.files.get('csv')

        # TODO: Check for dataset:
        # data = request.form.to_dict(flat=True)
        client = bigquery.Client(current_app.config['PROJECT_ID'])
        dataset = client.dataset('Gift')
        # dataset.create()  # API request

        table = dataset.table(id, SCHEMA)
        if table.exists():
            table.delete()
            table.create()

        # Save file to cloud via blob
        public_url = storage.upload_file(
            csvFile.read(),
            csvFile.filename,
            csvFile.content_type)

        response = urllib2.urlopen(public_url)
        table.upload_from_file(response, source_format='CSV', skip_leading_rows=1)

        csvResponse = 'The CSV was for report ' + report['reportName'] + ' was successfully added to Greasebelt. ' + \
                      'Please click here to request a sync with Fundtracker.'

    else:
        # Authentication is provided by the 'gcloud' tool when running locally
        # and by built-in service accounts when running on GAE, GCE, or GKE.
        # See https://developers.google.com/identity/protocols/application-default-credentials for more information.
        credentials = GoogleCredentials.get_application_default()

        # Construct the bigquery service object (version v2) for interacting
        # with the API. You can browse other available API services and versions at
        # https://developers.google.com/api-client-library/python/apis/
        service = discovery.build('bigquery', 'v2', credentials=credentials)

        # TODO: Change placeholders below to appropriate parameter values for the 'list' method:
        # * Project ID of the table to read
        projectId = current_app.config['PROJECT_ID']
        # * Dataset ID of the table to read
        datasetId = 'Gift'
        # * Table ID of the table to read
        tableId = id

        time.sleep(2)  # Used to allow for the creation of the new table
        bq_request = service.tabledata().list(projectId=projectId, datasetId=datasetId, tableId=tableId)
        data = bq_request.execute()

        rowCollection = []
        headerRow = []
        csvFile = open('/Users/soliagha/Projects/debug-venv/gb-debug/bookshelf/csv/test-export.csv', 'w+')
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

        return render_template("csv.html", report=report, csvResponse=csvResponse, csvRender=csvRender, public_url=public_url)
    return render_template("csv.html", report=report)


@crud.route('/<id>/view_csv', methods=['GET', 'POST'])
def view_csv(id):

    return upload_csv(id)


# [START upload_image_file]
def upload_image_file(file):
    """
    Upload the user-uploaded file to Google Cloud Storage and retrieve its
    publicly-accessible URL.
    """
    if not file:
        return None

    public_url = storage.upload_file(
        file.read(),
        file.filename,
        file.content_type
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
    organizationName = ''
    reportName = ''

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

        # If an image was uploaded, update the data to point to the new image.
        # [START image_url]
        reportFile = upload_image_file(request.files.get('image'))

        # [END image_url]

        # [START image_url2]
        if reportFile:
            data['reportUrl'] = reportFile[0]
            data['reportName'] = reportFile[1]
        # [END image_url2]

        report = get_model().create(data)

        return redirect(url_for('.view', id=report['id']))

    return render_template("form.html", action="Add", report={})


@crud.route('/<id>/edit', methods=['GET', 'POST'])
def edit(id):
    report = get_model().read(id)

    if request.method == 'POST':
        data = request.form.to_dict(flat=True)


        image_url = upload_image_file(request.files.get('image'))

        if image_url:
            data['reportUrl'] = image_url

        report = get_model().update(data, id)

        return redirect(url_for('.view', id=report['id']))

    return render_template("form.html", action="Edit", report=report)


@crud.route('/<id>/delete')
def delete(id):

    report = get_model().read(id)

    client = bigquery.Client(current_app.config['PROJECT_ID'])
    dataset = client.dataset('Gift')
    dataset.table(id).delete()

    storage.delete_file(report['reportUrl'])

    get_model().delete(id)

    return redirect(url_for('.list'))
