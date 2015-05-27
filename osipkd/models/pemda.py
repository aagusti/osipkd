from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    SmallInteger,
    Text,
    DateTime,
    String,
    ForeignKey,
    text,
    UniqueConstraint,
    
    )
    
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
    relationship,backref    )
from ..models import Base, DBSession, CommonModel, NamaModel

def unitfinder(userid, request):
    if userid and hasattr(request, 'user') and request.user:
        units = [('%s,%s' % (u.kode,u.sub_unit)) for u in request.user.units]
        return units
    return []
    
class UrusanModel(Base, NamaModel):
    __tablename__  = 'urusans'
    __table_args__ = {'extend_existing':True, 
                      'schema' : 'pemda',}

class UnitModel(Base, NamaModel):
    __tablename__  = 'units'
    __table_args__ = {'extend_existing':True, 
                      'schema' : 'pemda',}
                       
    urusan_id = Column(Integer, ForeignKey('pemda.urusans.id'))
    kategori = Column(String(32))
    singkat  = Column(String(32))
    level_id  = Column(SmallInteger)
    header_id = Column(SmallInteger)
    urusan_id = Column(Integer, ForeignKey('pemda.urusans.id'))
    units     = relationship("UrusanModel", backref="units")

class UserUnitModel(Base, CommonModel):
    __tablename__  = 'user_units'
    __table_args__ = {'extend_existing':True, 
                      'schema' : 'pemda',}
                       
    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    unit_id = Column(Integer, ForeignKey('pemda.units.id'), primary_key=True)
    sub_unit = Column(SmallInteger, nullable=False)
    units     = relationship("UnitModel", backref="users")
    users     = relationship("User", backref="units")
    
    @classmethod
    def query_user_id(cls, user_id):
        return DBSession.query(cls).filter_by(user_id = user_id)

    @classmethod
    def ids(cls, user_id):
        r = ()
        units = DBSession.query(cls.unit_id,cls.sub_unit, UnitModel.kode
                     ).join(UnitModel).filter(cls.unit_id==UnitModel.id,
                            cls.user_id==user_id).all() 
        for unit in units:
            if unit.sub_unit:
                rows = DBSession.query(UnitModel.id).filter(UnitModel.kode.ilike('%s%%' % unit.kode)).all()
            else:
                rows = DBSession.query(UnitModel.id).filter(UnitModel.kode==unit.kode).all()
            for i in range(len(rows)):
                print '***', rows[i]
                r = r + (rows[i])
        return r
        
    @classmethod
    def unit_granted(cls, user_id, unit_id):
        
        print 'A*******',  user_id, unit_id
        units = DBSession.query(cls.unit_id,cls.sub_unit, UnitModel.kode
                     ).join(UnitModel).filter(cls.unit_id==UnitModel.id,
                            cls.user_id==user_id).all() 
        for unit in units:
            print 'B*******',  unit_id, unit
            if unit.sub_unit:
                rows = DBSession.query(UnitModel.id).filter(UnitModel.kode.ilike('%s%%' % unit.kode)).all()
            else:
                rows = DBSession.query(UnitModel.id).filter(UnitModel.kode==unit.kode).all()
            for i in range(len(rows)):
                if int(rows[i][0])  == int(unit_id):
                    return True
        return False
        
    @classmethod
    def get_filtered(cls, request):
        filter = "'%s' LIKE pemda.units.kode||'%%'" % request.session['unit_kd']
        q1 = DBSession.query(UnitModel.kode, UserUnitModel.sub_unit).join(UserUnitModel).\
                       filter(UserUnitModel.user_id==request.user.id,
                              UserUnitModel.unit_id==UnitModel.id,
                              text(filter))
        return q1.first()
        
class Rekening(NamaModel, Base):
    __tablename__ = 'rekenings'
    __table_args__= (UniqueConstraint('kode', 'tahun', name='rekening_uq'),
                      {'extend_existing':True, 
                      'schema' : 'pemda',})
    tahun = Column(Integer)
    #created  = Column(DateTime, nullable=False, default=datetime.utcnow)
    level_id  = Column(SmallInteger)
    parent_id  = Column(BigInteger, ForeignKey('pemda.rekenings.id'))
    disabled = Column(SmallInteger, nullable=False, default=0)
    children   = relationship("Rekening", backref=backref('parent', remote_side='Rekening.id'))
    
    @classmethod
    def get_next_level(cls,id):
        return cls.query_id(id).first().level_id+1
        
    