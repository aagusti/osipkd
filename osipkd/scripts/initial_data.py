import os
import csv
from types import DictType
from sqlalchemy import (
    Table,
    MetaData,
    )
from data.user import UserData
from data.routes import RouteData
from data.apps import AppsData
from data.unit import UnitData
from data.rekening import RekeningData
from data.urusan import UrusanData

from DbTools import (
    get_pkeys,
    execute,
    set_sequence,
    split_tablename,
    )
from ..models import (
    Base,
    BaseModel,
    CommonModel,
    DBSession,
    User,
    )


fixtures = [
    ('users', UserData),
    ('routes', RouteData),
    ('pemda.urusans', UrusanData),
    ('pemda.units', UnitData),
    ('pemda.rekenings', RekeningData),
    ]

def insert():
    insert_(fixtures)
    
def insert_(fixtures): 
    engine = DBSession.bind
    metadata = MetaData(engine)
    tablenames = []
    for tablename, data in fixtures:
        if 'csv' in data:
            data['data'] = csv2fixture(data['csv'])
        if tablename == 'users':
            T = User
            table = T.__table__
        else:
            schema, tablename_ = split_tablename(tablename)
            table = Table(tablename_, metadata, autoload=True, schema=schema)
            class T(Base, BaseModel, CommonModel):
                __table__ = table
        if type(data) == DictType:
            options = data['options']        
            data = data['data']
        else:
            options = []
        if options and 'insert if not exists' not in options:
            q = DBSession.query(T).limit(1)
            if q.first():
                continue
        if 'delete first' in options:
            engine.execute('DELETE FROM {table}'.format(table=tablename)) #DBSession.Query(table).delete()
            DBSession.flush()
        tablenames.append(tablename)                
        keys = get_pkeys(table)
        id = 1
        print '----------->', tablename, data
        for d in data:
            filter_ = {}
            for key in keys:
                if key in d:
                    val = d[key]
                else:
                    if key=='id':
                      d.update({key:id})
                      val = id
                filter_[key] = val
            
            if filter_:
                q = DBSession.query(T).filter_by(**filter_)
                if q.first():
                    continue
            tbl = T()
            
            tbl.from_dict(d)
            print '----------->', tablename, d
            
            if tablename == 'users' and 'password' in d:
                tbl.password = d['password']
            DBSession.add(tbl)
            id+=1
            
    DBSession.flush()
    update_sequence(tablenames)

# Perbaharui nilai sequence    
def update_sequence(tablenames):
    engine = DBSession.bind
    metadata = MetaData(engine)
    for item in fixtures:
        tablename = item[0]
        if tablename not in tablenames:
            continue
        schema, tablename = split_tablename(tablename)
        class T(Base):
            __table__ = Table(tablename, metadata, autoload=True, schema=schema)
        set_sequence(T)
        
# Fixture from CSV file
def csv2fixture(filename):
    base_dir = os.path.split(__file__)[0]
    filename = os.path.join(base_dir, 'data', filename)
    csvfile = open(filename)    
    reader = csv.DictReader(csvfile)
    data = list(reader)
    csvfile.close()
    return data
