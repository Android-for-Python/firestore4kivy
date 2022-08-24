Firestore4Kivy
==============

*A very basic, lightweight, machine independent Firestore API*

# Introduction

The package contains methods to authorize and perform CRUD operations on a Firestore database. The data saved and retrieved is a *constrained* Python dict, constrained by the datatypes and resources available on Firestore. The implementation uses REST APIs.

Data is saved in a 'document' in a 'collection'. Firestore security rules that enable authorized public access to a document, and authorized private access to a document are compatible.

Nothing in this package is Kivy specific, however the motivation for the package is mobile devices and for Python that likely means Kivy. 

# Example Usage

Assuming a Firebase account has been created, a Firestore project has been configured, and the [Firebase all authenticated users rule](https://firebase.google.com/docs/rules/basics#all_authenticated_users) is specified.

**In a real usage each access would be in its own thread.**

Obtain the APIKEY and PROJECT_ID of a Firebase project. 

```python
from firestore4kivy import Authorize, Firestore
from math import pi

auth = Authorize(APIKEY)
success, response = auth.sign_in_with_email('email', 'password')

if success:
    db = Firestore(PROJECT_ID)
    db.enable_database(response)
    
    data = {'name' : 'Random Hacker', 'favorite number' : pi }
    success, result, update_time = db.create('collection', 'document', data)
    if success:
       success, result, update_time = db.read('collection', 'document')
       if success:
           field_to_update = {'favorite number' : 0 }
           success, result, update_time = db.update('collection', 'document', field_to_update)
           print(result) #{'name' : 'Random Hacker', 'favorite number' : 0 }
```

See also the [example](https://github.com/Android-for-Python/cloud_storage_examples/tree/main/rest_firestore_example).


# Install

### Desktop
```
pip3 install firestore4kivy
```

### Buildozer

```
requirements = python3, kivy, firestore4kivy, requests, urllib3, charset-normalizer, idna, certifi

android.permissions = INTERNET
```

### kivy-ios

```
toolchain pip install firestore4kivy
```

# Firestore

## Checklist

This checklist is not a substitute for reading the Firebase documentation. See the [Firebase quick start](https://firebase.google.com/docs/firestore/quickstart), and [Firebase documentation](https://firebase.google.com/docs).

 - Create a Firebase account and project.
   - This generates the Project ID you will need for client apps.

 - Create API Key
   - `Build->Authentication->Get started->sign-in method->Email/Password->Enable->Save`

 - Firestore Database->Create Database
   - Select security rules.
   - Edit and publish new security rules.
   - Select a geographic location for the server.
   - Allow a few minutes for changes to propagate.

## Security Rules

Successful implementation requires that the [security rules](https://firebase.google.com/docs/rules/basics) are correctly implemented. **The default rules deny access and must be changed.** For development only, you can use the [all authenticated users rule](https://firebase.google.com/docs/rules/basics#all_authenticated_users). As the name suggests this requires that the user is signed in.

Private documents will require the [content-owner only access rule.](https://firebase.google.com/docs/rules/basics#content-owner_only_access).

In practice the rules may be some hybrid, see the [rules for the example](https://github.com/Android-for-Python/cloud_storage_examples/tree/main/rest_firestore_example#specify-the-firestore-database-rules).

## Constraints

This section is not a substitute for reading [Firestore usage and limits](https://firebase.google.com/docs/firestore/quotas).

Some highlights:

- The data dict values **may** contain `None` or values with Python data types: `bool, int, float, str, bytes`. The dict may also contain three classes provided to access data types available in Firestore but not in Python, there are `GeoPoint, TimeStamp, Reference`.

- The data dict **may not** contain values with Python data types: `bytearray, memoryview, tuple, complex, range, frozenset, set`, or any class other than the three that enable Firestore data types.

- A dict key is always cast to a string. There is potential for a conflict if you use integers and strings as dict keys.

- A list may not contain a list as an element.

- A document may have a maximum of slightly less than 20k indices (sum of all keys and all list lengths).

- A document may have a maximum size of slightly less than 1MB.

If you are uncertain about violating Firestore constraints, as a test you can manually create your data structure in the Firebase console.

# API

**The methods must be called from a thread. If this is not done the Kivy UI will freeze for an undetermined time.** A general example of using threads is [documented](https://github.com/Android-for-Python/Android-for-Python-Users#threads).

The package contains an Authorize class, a Firestore class, and three classes to access custom Firestore data types.

## Authorize

All methods return a tuple of two values, success and response. If success is True, response is a dict. If success is False, response is an error message string.

A user initially signs in and the app saves a refresh token. On restart, resume, or after a timeout the app re-signs in using the token. Firestore will time out 3600 seconds after the last sign in. A sign in response contains the refresh token (save it), and data to enable Firestore (re-enable with each new response).

### Authorize Basic Usage

```python
from firestore4kivy import Authorize

# Instantiate with an APIKEY

auth = Authorize(APIKEY)

# sign in

success, response = auth.sign_in_with_email('user', 'password')
```

### Authorize API

```python
    def create_user_with_email(self, email, password):
        return success, response
         
    def sign_in_with_email(self, email, password):
        return success, response

    def sign_in_with_token(self, refresh_token):
        return success, response

    def delete_user(self, response):
        return success, response
```

## Firestore

All methods except enable_database return a tuple of three values, success, response, and update time. If success is True, response is a dict. If success is False, response is an error message string.

### Firestore Basic Usage

```python
from firestore4kivy import Firestore

# Instantiate with an PROJECT_ID

db = Firestore(PROJECT_ID)

# Enable the database with the response from sign in
db.enable_database(response)

# Create Document

data = {'name' : 'Joe', 'age' : 99}
success, response, update_time = db.create('collection', 'document', data)
```

### Firestore API

#### Enable_database

The auth argument is the response from Authorize api calls.

```python
    def enable_database(self, auth):
```

#### Create, Read, Delete

The `collection` and `document` arguments are strings. The `data` argument is a dict.

```python
    def create(self, collection, document, data):
        return success, response, update_time

    def read(self, collection, document):
        return success, response, update_time

    def delete(self, collection, document):
        return success, response, update_time
```

To create a private document the collection or document is set to `None`, the UserId will be substituted. This enables use of the Firestore the private document rule.

#### Update

The `collection` and `document` arguments are strings. The `replace`, `delete`, and callback method arguments are dicts. Examples below.

```python
    def update(self, collection, document, replace = {}, delete ={}, callback=None):
        return success, response, update_time
```

The `update()` method specifies changes to a created dict. It has three arguments used to update the document contents: replace, delete, and callback. One or all may be specified, they are applied in the above order.

Update is a secure read-modify-write operation. It ensures that another user will not corrupt the operation, the cost will be increased latency with heavily used shared documents. Single updates take fractions of a second, an update taking several seconds is a sign there are an excessive number of concurrent users and a failed update is possible. Do not implement `update()` on a shared document if you expect heavy concurrent usage.

In a Python dict, a list is atomic. To access list elements we use a list of tuples `[(index, new_value), (index, new_value),.... ] `, and specify the semantics as accessing list elements in a dict. Out of range indices are ignored.

Modification dicts are hierarchical. Check that root and intermediate dict keys are only specified once, otherwise one key will overwrite the other.

 - replace: a dict of key value pairs to replace. Pairs that do not exist in the original document are created. An empty dict specifies no modification. Special case: a tuple representing a list index equal to list length implements append(). An example replace dict (taken from the example where you can find the dict to be modified):

```python
                                                     # Equivalent statements
        replace_these = {'b' : False,                # ['b'] = False
                         'd' : {'c' : -43 ,          # ['d']['c'] = -43
                                'e' : [-10,-20,-30]},# ['d']['e'] =[-10,-20,-30]
                         'new' : True,               # ['new'] = True
                         'a' : [(1,'negative'),      # ['a'][1] = 'negative'
                                (4,'new')],}         # ['a'].append('new')
        # Note that for example ['d']['c'] and ['d']['e'] are hierarchical in the dict.
```
 
 - delete: a dict of keys to remove, the values should be empty except when specifying hierarchy. Keys that do not exist are ignored. An empty dict removes no keys. A delete of multiple list elements in the same list does not depend on lexical order (unlike the equivalent statements). An example delete dict:

```python
                                                     # Equivalent statements
        delete_these =  {'f':'',                     # pop('f')
                         'd': {'d' : {'aa': ''}},    # ['d']['d'].pop('aa')
                         'a': [(0,''),               # d['a'].pop(0)
                               (3, {'yes': ''})] }   # d['a'][2].pop('yes')
```

 - callback: a user supplied method that has the dict of modified data as an argument. It can be used to implment a state machine, or for debugging use a print statement to see the modified dict. An example of a state machine:

```python
    def counter(self, data):
        if 'counter' in data:
            data['counter'] += 1
        else:
            data['counter'] = 0

```

Implement as:

```python
    success, response, update_time =\
        db.update('secrets', None, replace_these, delete_these, self.couner)
```

## GeoPoint, TimeStamp, and Reference

The package provides three classes to access data types that exist in Firestore but not in Python.

All are written with initialize parameters, and read by a get() method. 

```python
from firestore4kivy import GeoPoint, Timestamp, Reference

# Latitude and longitude take there usual range

GeoPoint(latitude, longitude).get() == { 'latitude' : latitude, 'longitude' :longitude}

# TimeStamp is a Firestore compatible ISO 8601 string

TimeStamp('2000-01-01T00:00:00Z').get() == '2000-01-01T00:00:00Z'

# Reference to a Firestore document that must exist

Reference('projects/{project}/databases/(default)/documents/{collection}/{document}).get() == 'projects/{project}/databases/(default)/documents/{collection}/{document}

```
