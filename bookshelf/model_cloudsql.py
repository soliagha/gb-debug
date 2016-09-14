
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy

builtin_list = list


db = SQLAlchemy()


def init_app(app):
    db.init_app(app)


def from_sql(row):
    """Translates a SQLAlchemy model instance into a dictionary"""
    data = row.__dict__.copy()
    data['id'] = row.id
    data.pop('_sa_instance_state')
    return data


class Report(db.Model):
    __tablename__ = 'reports'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255))
    organizationName = db.Column(db.String(255))
    organizationID = db.Column(db.String(255))
    startDate = db.Column(db.String(255))
    endDate = db.Column(db.String(255))
    reportName = db.Column(db.String(255))
    reportUrl = db.Column(db.String(255))
    language = db.Column(db.String(255))
    csvUrl = db.Column(db.String(255))
    createdBy = db.Column(db.String(255))
    createdById = db.Column(db.String(255))

    def __repr__(self):
        return "<Report(title='%s', organizationName=%s)" % (self.title, self.organizationName)


def list(limit=10, cursor=None, search=None):
    cursor = int(cursor) if cursor else 0

    if search:
        query = (Report.query
                .order_by(Report.organizationName)
                .filter(Report.organizationName.like('%' + search['organizationName'] + '%'))
                .filter(Report.organizationID.like('%' + search['organizationID'] + '%'))
                .filter(Report.reportName.like('%' + search['reportName'] + '%'))
                .filter(Report.startDate.like('%' + search['startDate'] + '%'))
                .filter(Report.endDate.like('%' + search['endDate'] + '%'))
                .limit(limit)
                .offset(cursor))
    else:
        query = (Report.query
                .order_by(Report.organizationName)
                .limit(limit)
                .offset(cursor))


    reports = builtin_list(map(from_sql, query.all()))

    next_page = cursor + limit if len(reports) == limit else None
    return (reports, next_page)


def read(id):
    result = Report.query.get(id)
    if not result:
        return None
    return from_sql(result)


def create(data):
    report = Report(**data)
    db.session.add(report)
    db.session.commit()
    return from_sql(report)


def update(data, id):
    report = Report.query.get(id)
    for k, v in data.items():
        setattr(report, k, v)
    db.session.commit()
    return from_sql(report)


def delete(id):
    Report.query.filter_by(id=id).delete()
    db.session.commit()


def _create_database():
    """
    If this script is run directly, create all the tables necessary to run the
    application.
    """
    app = Flask(__name__)
    app.config.from_pyfile('../config.py')
    init_app(app)
    with app.app_context():
        db.create_all()
    print("All tables created")


if __name__ == '__main__':
    _create_database()
