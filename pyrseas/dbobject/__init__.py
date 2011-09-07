# -*- coding: utf-8 -*-
"""
    pyrseas.dbobject
    ~~~~~~~~~~~~~~~~

    This defines two low level classes and an intermediate class.
    Most Pyrseas classes are derived from either DbObject or
    DbObjectDict.
"""
import string


VALID_FIRST_CHARS = string.lowercase + '_'
VALID_CHARS = string.lowercase + string.digits + '_$'


def quote_id(name):
    """Quotes an identifier if necessary.

    :param name: string to be quoted

    :return: possibly quoted string
    """
    # TODO: keywords
    regular_id = True
    if not name[0] in VALID_FIRST_CHARS:
        regular_id = False
    else:
        for ltr in name[1:]:
            if ltr not in VALID_CHARS:
                regular_id = False
                break

    return regular_id and name or '"%s"' % name


def split_schema_obj(obj, sch=None):
    """Return a (schema, object) tuple given a possibly schema-qualified name

    :param obj: object name or schema.object
    :param sch: schema name (defaults to 'public')
    :return: tuple
    """
    qualsch = sch
    if sch == None:
        qualsch = 'public'
    if '.' in obj:
        (qualsch, obj) = obj.split('.')
    if obj[:1] == '"' and obj[-1:] == '"':
        obj = obj[1:-1]
    if sch != qualsch:
        sch = qualsch
    return (sch, obj)


class DbObject(object):
    "A single object in a database catalog, e.g., a schema, a table, a column"

    keylist = ['name']
    objtype = ''

    def __init__(self, **attrs):
        """Initialize the catalog object from a dictionary of attributes

        :param attrs: the dictionary of attributes

        Non-key attributes without a value are discarded.
        """
        for key, val in attrs.items():
            if val or key in self.keylist:
                setattr(self, key, val)

    def extern_key(self):
        """Return the key to be used in external maps for this object

        :return: string
        """
        return '%s %s' % (self.objtype.lower(), self.name)

    def key(self):
        """Return a tuple that identifies the database object

        :return: a single value or a tuple
        """
        lst = [getattr(self, k) for k in self.keylist]
        return len(lst) == 1 and lst[0] or tuple(lst)

    def identifier(self):
        """Returns a full identifier for the database object

        :return: string
        """
        return quote_id(self.__dict__[self.keylist[0]])

    def to_map(self):
        """Convert an object to a YAML-suitable format

        :return: dictionary
        """
        dct = self.__dict__.copy()
        for k in self.keylist:
            del dct[k]
        return {self.extern_key(): dct}

    def comment(self):
        """Return SQL statement to create COMMENT on object

        :return: SQL statement
        """
        if hasattr(self, 'description'):
            descr = "'%s'" % self.description
        else:
            descr = 'NULL'
        return "COMMENT ON %s %s IS %s" % (
            self.objtype, self.identifier(), descr)

    def drop(self):
        """Return SQL statement to DROP the object

        :return: SQL statement
        """
        return "DROP %s %s" % (self.objtype, self.identifier())

    def rename(self, newname):
        """Return SQL statement to RENAME the object

        :param newname: the new name for the object
        :return: SQL statement
        """
        return "ALTER %s %s RENAME TO %s" % (self.objtype, self.name, newname)

    def diff_map(self, inobj):
        """Generate SQL to transform an existing object

        :param inobj: a YAML map defining the new object
        :return: list of SQL statements

        Compares the object to an input object and generates SQL
        statements to transform it into the one represented by the
        input.
        """
        stmts = []
        stmts.append(self.diff_description(inobj))
        return stmts

    def diff_description(self, inobj):
        """Generate SQL statements to add or change COMMENTs

        :param inobj: a YAML map defining the input object
        :return: list of SQL statements
        """
        stmts = []
        if hasattr(self, 'description'):
            if hasattr(inobj, 'description'):
                if self.description != inobj.description:
                    self.description = inobj.description
                    stmts.append(self.comment())
            else:
                del self.description
                stmts.append(self.comment())
        else:
            if hasattr(inobj, 'description'):
                self.description = inobj.description
                stmts.append(self.comment())
        return stmts


class DbSchemaObject(DbObject):
    "A database object that is owned by a certain schema"

    def identifier(self):
        """Return a full identifier for a schema object

        :return: string
        """
        return self.qualname()

    def qualname(self):
        """Return the schema-qualified name of the object

        :return: string

        No qualification is used if the schema is 'public'.
        """
        return self.schema == 'public' and quote_id(self.name) \
            or "%s.%s" % (quote_id(self.schema), quote_id(self.name))

    def unqualify(self):
        """Adjust the schema and table name if the latter is qualified"""
        if hasattr(self, 'table') and '.' in self.table:
            (sch, self.table) = split_schema_obj(self.table, self.schema)

    def drop(self):
        """Return a SQL DROP statement for the schema object

        :return: SQL statement
        """
        if not hasattr(self, 'dropped') or not self.dropped:
            self.dropped = True
            return "DROP %s %s" % (self.objtype, self.identifier())
        return []

    def rename(self, newname):
        """Return a SQL ALTER statement to RENAME the schema object

        :param newname: the new name of the object
        :return: SQL statement
        """
        return "ALTER %s %s RENAME TO %s" % (self.objtype, self.qualname(),
                                             newname)

    def set_search_path(self):
        """Return a SQL SET search_path if not in the 'public' schema"""
        stmt = ''
        if self.schema != 'public':
            stmt = "SET search_path TO %s, pg_catalog" % quote_id(self.schema)
        return stmt


class DbObjectDict(dict):
    """A dictionary of database objects, all of the same type"""

    cls = DbObject
    query = ''

    def __init__(self, dbconn=None):
        """Initialize the dictionary

        :param dbconn: a DbConnection object

        If dbconn is not None, the _from_catalog method is called to
        initialize the dictionary from the catalogs.
        """
        dict.__init__(self)
        self.dbconn = dbconn
        if dbconn:
            self._from_catalog()

    def _from_catalog(self):
        """Initialize the dictionary by querying the catalogs

        This is may be overriden by derived classes as needed.
        """
        for obj in self.fetch():
            self[obj.key()] = obj

    def fetch(self):
        """Fetch all objects from the catalogs using the class query

        :return: list of self.cls objects
        """
        if not self.dbconn.conn:
            self.dbconn.connect()
        data = self.dbconn.fetchall(self.query)
        return [self.cls(**dict(row)) for row in data]
