from email.utils import parseaddr
import xlrd
import os
import re
import csv
import io
import csv, codecs, cStringIO

from types import (
    IntType,
    LongType,
    )
from datetime import (
    datetime,
    timedelta,
    )
import locale
import pytz
from pyramid.threadlocal import get_current_registry    


################
# Phone number #
################
MSISDN_ALLOW_CHARS = map(lambda x: str(x), range(10)) + ['+']

def get_msisdn(msisdn, country='+62'):
    for ch in msisdn:
        if ch not in MSISDN_ALLOW_CHARS:
            return
    try:
        i = int(msisdn)
    except ValueError, err:
        return
    if not i:
        return
    if len(str(i)) < 7:
        return
    if re.compile(r'^\+').search(msisdn):
        return msisdn
    if re.compile(r'^0').search(msisdn):
        return '%s%s' % (country, msisdn.lstrip('0'))

################
# Money format #
################
def should_int(value):
    int_ = int(value)
    return int_ == value and int_ or value

def thousand(value, float_count=None):
    if float_count is None: # autodetection
        if type(value) in (IntType, LongType):
            float_count = 0
        else:
            float_count = 2
    return locale.format('%%.%df' % float_count, value, True)

def money(value, float_count=None, currency=None):
    if value < 0:
        v = abs(value)
        format_ = '(%s)'
    else:
        v = value
        format_ = '%s'
    if currency is None:
        currency = locale.localeconv()['currency_symbol']
    s = ' '.join([currency, thousand(v, float_count)])
    return format_ % s

###########    
# Pyramid #
###########    
def get_settings():
    return get_current_registry().settings
    
def get_timezone():
    settings = get_settings()
    return pytz.timezone(settings.timezone)

########    
# Time #
########
one_second = timedelta(1.0/24/60/60)
TimeZoneFile = '/etc/timezone'
if os.path.exists(TimeZoneFile):
    DefaultTimeZone = open(TimeZoneFile).read().strip()
else:
    DefaultTimeZone = 'Asia/Jakarta'

def as_timezone(tz_date):
    localtz = get_timezone()
    if not tz_date.tzinfo:
        tz_date = create_datetime(tz_date.year, tz_date.month, tz_date.day,
                                  tz_date.hour, tz_date.minute, tz_date.second,
                                  tz_date.microsecond)
    return tz_date.astimezone(localtz)    

def create_datetime(year, month, day, hour=0, minute=7, second=0,
                     microsecond=0):
    tz = get_timezone()        
    return datetime(year, month, day, hour, minute, second,
                     microsecond, tzinfo=tz)

def create_date(year, month, day):    
    return create_datetime(year, month, day)
    
def create_now():
    tz = get_timezone()
    return datetime.now(tz)
    
################
# Months #
################
BULANS = (
    ('01', 'Januari'),
    ('02', 'Februari'),
    ('03', 'Maret'),
    ('04', 'April'),
    ('05', 'Mei'),
    ('06', 'Juni'),
    ('07', 'Juli'),
    ('08', 'Agustus'),
    ('09', 'September'),
    ('10', 'Oktober'),
    ('11', 'November'),
    ('12', 'Desember'),
    )
    
def get_months(request):
    return BULANS

def email_validator(node, value):
    name, email = parseaddr(value)
    if not email or email.find('@') < 0:
        raise colander.Invalid(node, 'Invalid email format')    
        
def row2dict(row):
    d = {}
    for column in row.__table__.columns:
        d[column.name] = str(getattr(row, column.name))

    return d        
    
    
def clean(s):
    r = ''
    for ch in s:
        if ch not in string.printable:
            ch = ''
        r += ch
    return r

def xls_reader(filename):    
    workbook = xlrd.open_workbook(filename)
    worksheet = workbook.sheet_by_name('potongan')
    num_rows = worksheet.nrows - 1
    num_cells = worksheet.ncols - 1
    curr_row = -1
    csv = []
    while curr_row < num_rows:
        curr_row += 1
        row = worksheet.row(curr_row)
        curr_cell = -1
        txt = []
        while curr_cell < num_cells:
            curr_cell += 1
            # Cell Types: 0=Empty, 1=Text, 2=Number, 3=Date, 4=Boolean, 5=Error, 6=Blank
            cell_type = worksheet.cell_type(curr_row, curr_cell)
            cell_value = worksheet.cell_value(curr_row, curr_cell)
            if cell_type==1 or cell_type==2:
                try:
                    cell_value = str(cell_value)
                except:
                    cell_value = '0'
            else:
                cell_value = clean(cell_value)
                
            if curr_cell==0 and cell_value.strip()=="Tanggal":
                curr_cell=num_cells
            elif curr_cell==0 and cell_value.strip()=="":
                curr_cell = num_cells
                curr_row = num_rows
            else:
                txt.append(cell_value)
        if txt:
            csv.append(txt)
    return csv        


class UTF8Recoder:
    """
    Iterator that reads an encoded stream and reencodes the input to UTF-8
    """
    def __init__(self, f, encoding):
        self.reader = codecs.getreader(encoding)(f)

    def __iter__(self):
        return self

    def next(self):
        return self.reader.next().encode("utf-8")

class UnicodeReader:
    """
    A CSV reader which will iterate over lines in the CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        f = UTF8Recoder(f, encoding)
        self.reader = csv.reader(f, dialect=dialect, **kwds)

    def next(self):
        row = self.reader.next()
        return [unicode(s, "utf-8") for s in row]

    def __iter__(self):
        return self

class UnicodeWriter:
    """
    A CSV writer which will write rows to CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        # Redirect output to a queue
        self.queue = cStringIO.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        self.writer.writerow([s.encode("utf-8") for s in row])
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        # ... and reencode it into the target encoding
        data = self.encoder.encode(data)
        # write to the target stream
        print data
        self.stream.write(data)
        # empty queue
        self.queue.truncate(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)
            
class CSVRenderer(object):
   def __init__(self, info):
      pass

   def __call__(self, value, system):
      """ Returns a plain CSV-encoded string with content-type
      ``text/csv``. The content-type may be overridden by
      setting ``request.response.content_type``."""

      request = system.get('request')
      if request is not None:
         response = request.response
         ct = response.content_type
         if ct == response.default_content_type:
            response.content_type = 'text/csv'

      fout = io.BytesIO() #StringIO()
      fcsv = csv.writer(fout, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
      #fcsv = UnicodeWriter(fout, delimiter=',', quotechar=',', quoting=csv.QUOTE_MINIMAL)
      #print value.get('header', [])
      fcsv.writerow(value.get('header', []))
      fcsv.writerows(value.get('rows', []))

      return fout.getvalue()    