import sys
from datetime import datetime
from sqlalchemy import (
    Column,
    Integer, SmallInteger,
    Text,
    DateTime,
    func,
    String,
    ForeignKey,
    )
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
    relationship,
    backref
    )
from zope.sqlalchemy import ZopeTransactionExtension
import transaction
import ziggurat_foundations.models
from ziggurat_foundations.models import BaseModel, UserMixin, GroupMixin
from ziggurat_foundations.models import GroupPermissionMixin, UserGroupMixin
from ziggurat_foundations.models import GroupResourcePermissionMixin, ResourceMixin
from ziggurat_foundations.models import UserPermissionMixin, UserResourcePermissionMixin
from ziggurat_foundations.models import ExternalIdentityMixin
from ziggurat_foundations import ziggurat_model_init
from pyramid.security import (
    Allow,
    Authenticated,
    Everyone,
    ALL_PERMISSIONS
    )
from ..tools import as_timezone


DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()


##############
# Base model #
##############
class CommonModel(object):
    def to_dict(self): # Elixir like
        values = {}
        for column in self.__table__.columns:
            values[column.name] = getattr(self, column.name)
        return values
        
    def from_dict(self, values):
        for column in self.__table__.columns:
            if column.name in values:
                setattr(self, column.name, values[column.name])

    def as_timezone(self, fieldname):
        date_ = getattr(self, fieldname)
        return date_ and as_timezone(date_) or None


class DefaultModel(CommonModel):
    id = Column(Integer, primary_key=True)

    def save(self):
        if self.id:
            #Who knows another user edited, so use merge ()
            DBSession.merge(self)
        else:
            DBSession.add(self)    
        
    @classmethod
    def query(cls):
        return DBSession.query(cls)

    @classmethod
    def query_id(cls, id):
        return cls.query().filter_by(id=id)
        
    @classmethod
    def get_by_id(cls, id):
        return cls.query_id(id).first()                

    @classmethod
    def delete(cls, id):
        cls.query_id(id).delete()

class Group(GroupMixin, Base, CommonModel):
    pass

class GroupPermission(GroupPermissionMixin, Base):
    pass


class UserGroup(UserGroupMixin, Base, CommonModel):
    @classmethod
    def get_by_email(cls, email):
        user = User.get_by_email(email)
        return cls.get_by_user(user)
        
    @classmethod
    def _get_by_user(cls, user):
        return DBSession.query(cls).filter_by(user_id=user.id).all()
        
    @classmethod
    def get_by_user(cls, user):
        groups = []
        for g in cls._get_by_user(user):
            groups.append(g.group_id)
        return groups
                
    @classmethod
    def set_one(cls, session, user, group):
        member = DBSession.query(cls).filter_by(user_id=user.id, group_id=group.id)
        try:
            member = member.one()
        except NoResultFound:
            member = cls(user_id=user.id, group_id=group.id)
            DBSession.add(member)
            transaction.commit()
        
    @classmethod
    def set_all(cls, user, group_ids=[]):
        if type(user) in [StringType, UnicodeType]:
            user = User.get_by_email(user)
        olds = cls._get_by_user(user)
        news = []
        for group_id in group_ids:
            group = DBSession.query(Group).get(group_id)
            member = cls.set_one(user, group)
            news.append(group)
        for old in olds:
            if old not in news:
                old.delete()
                DBSession.commit()
                
    @classmethod
    def get_by_group(cls, group):
        users = []
        for g in DBSession.query(cls).filter_by(group=group):
            users.append(g.user)
        return users                


class GroupResourcePermission(GroupResourcePermissionMixin, Base):
    pass

class Resource(ResourceMixin, Base, CommonModel):
    pass

class UserPermission(UserPermissionMixin, Base):
    pass

class UserResourcePermission(UserResourcePermissionMixin, Base):
    pass


class User(UserMixin, BaseModel, CommonModel, Base):
    last_login_date = Column(DateTime(timezone=True), nullable=True)
    registered_date = Column(DateTime(timezone=True),
                             nullable=False,
                             default=datetime.utcnow)
    #units = relationship("UnitModel"
    
    def _get_password(self):
        return self._password

    def _set_password(self, password):
        self._password = self.set_password(password)

    password = property(_get_password, _set_password)

    def get_groups(self):
        return UserGroup.get_by_user(self)

    def last_login_date_tz(self):
        return as_timezone(self.last_login_date)
        
    def registered_date_tz(self):
        return as_timezone(self.registered_date)
        
    def nice_username(self):
        return self.user_name or self.email

    @classmethod
    def get_by_email(cls, email):
        return DBSession.query(cls).filter_by(email=email).first()

    @classmethod
    def get_by_name(cls, name):
        return DBSession.query(cls).filter_by(user_name=name).first()        
        
    @classmethod
    def get_by_identity(cls, identity):
        if identity.find('@') > -1:
            return cls.get_by_email(identity)
        return cls.get_by_name(identity)        
            
class GroupRoutePermission(Base, CommonModel):
    __tablename__  = 'groups_routes_permissions'
    __table_args__ = {'extend_existing':True,}    
    route_id = Column(Integer, ForeignKey("routes.id"),nullable=False, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id"),nullable=False, primary_key=True)
    routes = relationship("Route", backref=backref('routepermission'))
    groups = relationship("Group",backref= backref('grouppermission'))
    
    
    
class ExternalIdentity(ExternalIdentityMixin, Base):
    pass

class AkarFactory(object):
    def __init__(self, request):
        self.__acl__ = [(Allow, 'Admin', ALL_PERMISSIONS), 
                        (Allow, Authenticated, 'view'),]
        
        for x, y in group_app_permissions:
            self.__acl__.append((Allow, x, y))
            
class RootFactory(object):
    def __init__(self, request):
        self.__acl__ = [(Allow, 'Admin', ALL_PERMISSIONS), 
                        (Allow, Authenticated, 'view'),]

class GajiFactory(RootFactory):
    def __init__(self, request):
        super(GajiFactory, self ).__init__(request)
        self.__acl__.append((Allow, 'g:gaji', 'read'))
        self.__acl__.append((Allow, 'g:gaji', 'add'))
        self.__acl__.append((Allow, 'g:gaji', 'edit'))
        self.__acl__.append((Allow, 'g:gaji', 'delete'))
        
        self.__acl__.append((Allow, 'g:bank', 'read'))
        self.__acl__.append((Allow, 'g:bank', 'add'))
        self.__acl__.append((Allow, 'g:bank', 'edit'))
        
        self.__acl__.append((Allow, 'g:bp', 'read'))
        self.__acl__.append((Allow, 'g:bp', 'add'))
        self.__acl__.append((Allow, 'g:bp', 'edit'))
        
        
class AdminFactory(RootFactory):
    def __init__(self, request):
        super(AdminFactory, self ).__init__(request)
        self.__acl__.append((Allow, 'g:admin', 'read'))
        self.__acl__.append((Allow, 'g:admin', 'add'))
        self.__acl__.append((Allow, 'g:admin', 'edit'))
        self.__acl__.append((Allow, 'g:admin', 'delete'))

        
class ResourceFactory(RootFactory):
    def __init__(self, request):
        super( ResourceFactory, self ).__init__(request)
        route = request.matched_route
        rname = route.name
       
        #self.resource = Resource.by_resource_name(rname)
        if not self.resource:
            request.session.flash('Anda tidak punya hak akses','error')
            raise HTTPNotFound()
        if self.resource and request.user:
            self.__acl__ = self.resource.__acl__
            for perm_user, perm_name in self.resource.perms_for_user(request.user):
                self.__acl__.append((Allow, perm_user, perm_name,))


class KodeModel(DefaultModel):
    kode = Column(String(32))
    disabled = Column(SmallInteger, nullable=False, default=0)
    created  = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated  = Column(DateTime, nullable=True)
    create_uid  = Column(Integer, nullable=False, default=1)
    update_uid  = Column(Integer, nullable=True)
    
    @classmethod
    def get_by_kode(cls,kode):
        return cls.query().filter_by(kode=kode).first()
        
    @classmethod
    def count(cls):
        return DBSession.query(func.count('*')).scalar()
    
    @classmethod
    def get_active(cls):
        return DBSession.query(cls).filter_by(disabled=0).all()
    
    
    
#class UraianModel(KodeModel):
#    uraian = Column(String(128))
#    @classmethod
#    def get_by_uraian(uraian):
#        return cls.query().filter_by(uraian=uraian).first()
        
#    @classmethod
#    def get_nama(uraian):
#        return cls.query().filter_by(uraian=uraian)


class NamaModel(KodeModel):
    nama = Column(String(128))
    
    @classmethod
    def get_by_nama(nama):
        return cls.query().filter_by(nama=nama).first()
        
    @classmethod
    def get_nama(nama):
        return cls.query().filter_by(nama=nama)

class Route(Base, NamaModel):
    __tablename__  = 'routes'
    __table_args__ = {'extend_existing':True}
    path      = Column(String(256), nullable=False)
    factory   = Column(String(256))
    perm_name = Column(String(16))
    
    
class App(Base, NamaModel):
    __tablename__  = 'apps'
    __table_args__ = {'extend_existing':True,}
    tahun = Column(Integer)
    
    @classmethod
    def count_active(cls):
        return DBSession.query(func.count(cls.id)).filter(cls.disabled==0).scalar()
    @classmethod
    def active_url(cls):
        return DBSession.query(cls.kode).filter(cls.disabled==0).first().kode
                        
def init_model():
    ziggurat_model_init(User, Group, UserGroup, GroupPermission, UserPermission,
                   UserResourcePermission, GroupResourcePermission, Resource,
                   ExternalIdentity, passwordmanager=None)
