import json
import requests
from requests.exceptions import Timeout
from time import sleep

####### Identity Toolkit Reference
# v1   https://cloud.google.com/identity-platform/docs/use-rest-api
# v3   apparently has no documentation, infer from language specific apis
#
####### Firestore REST Reference
# https://firebase.google.com/docs/firestore/reference/rest/
#
####### Firestore User Docs
# https://firebase.google.com/docs/firestore

#######
# Implements:
# Authorize, Firestore, GeoPoint, TimeStamp, and Reference classes.
#######


class Authorize:
    V1 = 'https://securetoken.googleapis.com/v1/'
    V3 = 'https://www.googleapis.com/identitytoolkit/v3/relyingparty/'

    def __init__(self, apikey):
        self.apikey = apikey
        self.timeout = 6.01

    def create_user_with_email(self, email, password):
        payload = json.dumps({'email': email, 'password': password,
                              'returnSecureToken': 'true'})
        url = self.V3 + 'signupNewUser?key=' + self.apikey
        try:
            return self.parse_result(requests.post(url, data=payload,
                                     timeout=self.timeout))
        except Exception as e:
            return False, 'ERROR: ' + str(e)
         
    def sign_in_with_email(self, email, password):
        payload = json.dumps({'email': email, 'password': password,
                              'returnSecureToken': 'true'})
        url = self.V3 + 'verifyPassword?key=' + self.apikey
        try:
            return self.parse_result(requests.post(url, data=payload,
                                     timeout=self.timeout))
        except Exception as e:
            return False, 'ERROR: ' + str(e)

    def sign_in_with_token(self, refresh_token):
        payload = json.dumps({'grantType': 'refresh_token',
                              'refreshToken': refresh_token})
        url = self.V1 + 'token?key=' + self.apikey
        try:
            success, response = self.parse_result(
                requests.post(url,data=payload,timeout=self.timeout))

            if success:
                # convert from v1 to v3
                return True, {'localId': response['user_id'],
                              'idToken': response['id_token'],
                              'refreshToken': response['refresh_token']}
            else:
                return False, response
        except Exception as e:
            return False, 'ERROR: ' + str(e)

    def delete_user(self, response):
        if response and isinstance(response, dict) and 'idToken' in response:
            payload = json.dumps({"idToken": response['idToken']})
            url = self.V3 + 'deleteAccount?key=' + self.apikey
            try:
                return self.parse_result(
                    requests.post(url, data=payload,timeout=self.timeout))

            except Exception as e:
                return False, 'ERROR: ' + str(e)
        else:
            return False, 'ERROR: delete_user(), incorrect argument.' 

    def parse_result(self,r):
        d = r.json()
        if r.status_code == 200:
            return True, d
        elif 'error' in d and 'message' in d['error']:
            return False, 'ERROR: ' + d['error']['message']
        else:
            return False, 'ERROR: ' + str(d)

class Firestore:

    def __init__(self, project_id):
        endpoint = 'https://firestore.googleapis.com/v1/'
        self.path = 'projects/' + project_id + '/databases/(default)/documents/'
        self.REST = endpoint + self.path
        self.timeout = (6.01, 60)

    def enable_database(self, auth):
        self.local_id = ''
        self.id_token = ''
        if auth and isinstance(auth, dict) and\
           'localId' in auth and 'idToken' in auth:
            self.local_id = auth['localId']
            self.id_token = auth['idToken']

    ########################
    # REST operations
    ########################

    # Create
    ########
    def create(self, collection, document, data):
        if not collection:
            collection = self.local_id
        if not document:
            document = self.local_id
        size = self.dict_size(data)
        if size > 19990:
            return  False, 'ERROR: ' +\
                'Dict contains too many elements (' + str(size) +\
                ') for Firestore.', ''
        request_path = self.REST + collection + '?documentId=' + document
        try:
            fs_data = {'fields' : self.dict_to_firestore(data, False)}
            payload=json.dumps(fs_data).encode("utf-8")
            r = requests.post(request_path, headers = self.build_headers(),
                              data = payload,timeout=self.timeout)
            return self.parse_result(r.json())
        except Exception as e:
            return False, 'ERROR: ' + str(e), ''

    # Read
    ########
    def read(self, collection, document):
        if not collection:
            collection = self.local_id
        if not document:
            document = self.local_id
        request_path = self.REST + collection + '/' + document
        try:
            r = requests.get(request_path, headers=self.build_headers(),
                             timeout=self.timeout)
            return self.parse_result(r.json())
        except Exception as e:
            return False, 'ERROR: ' + str(e), ''

    # Update
    ########
    # THIS METHOD MUST NOT BE CALLED FROM THE UI THREAD
    ########
    # Firestore implementation constraint:
    # Read/write locking is only available for oAuth2 authorization.
    # So we read, then write using read update time as a precondition.
    # Retry on fail. Afer 5 fast retries, use exponentially slower retry rate.
    # Apparently this is what the Google mobile SDKs do.
    # Reference:
    # https://groups.google.com/g/google-cloud-firestore-discuss/c/4yJsxHsAK1s
    ########
    def update(self, collection, document,
               replace = {}, delete = {}, callback = None):
        # replace: a dict of keys with new values to recursively assign.
        # delete: a dict of keys to recursively remove, leaf values ignored.
        #
        # lists are atomic, replace or delete changes the complete value.
        #
        # list elements are specified as a tuple of [(index, value), ...]
        # for delet the value is none or a dict or list.

        if not collection:
            collection = self.local_id
        if not document:
            document = self.local_id
        backoff = 0
        attempt = 0
        while True:
            # !!!!!sleep means this MUST be called in a non-UI thread
            sleep(backoff) 
            attempt += 1
            if attempt == 5:
                backoff = 1
            elif attempt > 5:
                backoff *= 1.5
            if backoff >= 60:
                return False, 'ERROR: Update of ' + collection + '/' +\
                    document + ' timed out.',''
            
            success, existing, update_time = self.read(collection, document)
            if success:
                self.dict_replace(existing, replace)  
                self.dict_pop(existing, delete)
                if callback:
                    callback(existing)
                size = self.dict_size(existing)
                if size > 19990:
                    return  False, 'ERROR: ' +\
                        'Dict contains too many elements (' + str(size) +\
                        ') for Firestore.', ''
                request_path = self.REST[:-1] + ':commit' 
                try:
                    fs_data = {}
                    fs_data['fields'] = self.dict_to_firestore(existing, False)
                    fs_data['name'] = self.path + collection + '/' + document
                    commit = {'writes':
                              [{'update': fs_data,
                                'currentDocument': {'updateTime': update_time}
                                }]}
                    payload=json.dumps(commit).encode("utf-8")
                    r = requests.post(request_path,
                                      headers=self.build_headers(),
                                      data = payload,
                                      timeout=self.timeout)
                    t = r.json()
                    if r.status_code == 400 and\
                       'error' in t and 'status' in t['error']:
                        if t['error']['status'] == 'FAILED_PRECONDITION':
                            continue
                    # Commit does not return what was written.
                    # We could read again, but we know that is not reliable.
                    # So we return what we wanted to write: this is a read, 
                    # modified and sanity checked.
                    return self.parse_result_update(t, existing) 
                except Exception as e:
                    return False, 'ERROR: ' + str(e), ''
            else:
                return False, existing, update_time

    # Delete
    ########
    def delete(self, collection, document):
        if not collection:
            collection = self.local_id
        if not document:
            document = self.local_id
        request_path = self.REST + collection + '/' + document
        try:
            r = requests.delete(request_path, headers=self.build_headers(),
                                timeout=self.timeout)
            if r.status_code == 200:
                return True, {}, ''
            else:
                return self.parse_result(r.json())
        except Exception as e:
            return False, 'ERROR: ' + str(e), ''

    ###################
    # Dict translation
    ###################

    def dict_to_firestore(self, data, parent_is_list):
    
        def map(ref, value):
            if value == None:
                return {'nullValue' : None} 
            elif isinstance(value, bool):
                return {'booleanValue' : value}
            elif isinstance(value, int):
                return {'integerValue' : str(value)}
            elif isinstance(value, float):
                return {'doubleValue' : value} 
            elif isinstance(value, str):
                return {'stringValue' : value}
            elif isinstance(value, bytes):
                return {'bytesValue' : value.decode('utf-8')} 
            elif isinstance(value, GeoPoint):
                return {'geoPointValue': value.get() }
            elif isinstance(value, TimeStamp):
                return {'timestampValue' : value.get() } 
            elif isinstance(value, Reference):
                return {'referenceValue' : value.get() } 
            elif isinstance(value, list):
                if parent_is_list:
                    assert False,\
                        'ERROR: Nested lists are not available in Firestore.' 
                    return {'nullValue' : None}
                return {'arrayValue' :
                        {'values' : self.dict_to_firestore(value, True)}}
            elif isinstance(value, dict):
                return {'mapValue' :
                        {'fields' : self.dict_to_firestore(value, False)}}
            elif isinstance(value, bytearray) or\
                 isinstance(value, memoryview) or\
                 isinstance(value, tuple) or\
                 isinstance(value, complex) or\
                 isinstance(value, range) or\
                 isinstance(value, frozenset) or\
                 isinstance(value, set):
                assert False, 'ERROR: ' + ref + 'value type ' +\
                    str(type(value)) + ' is not available in Firestore.' 
                return {'nullValue' : None}
            else:
                assert False,\
                    'ERROR: Class ' + str(type(value)) +\
                    ' is not available in Firestore.'
                return {'nullValue' : None} 
        
        if isinstance(data, dict):
            '''
            if len(data.keys()) > 20:
                assert False,\
                    'ERROR: A dict in Firestore must have 20 or less keys.'
            '''
            new_dict = {}
            #i = 0
            for key in data:
                #if i < 20:
                new_dict[str(key)] = map('Key "' + str(key) + '" ', data[key])
                #i += 1
            return new_dict
        elif isinstance(data, list):
            '''
            if len(data) > 20:
                assert False,\
                    'ERROR: A list in Firestore must have 20 or less elements.'
            '''
            new_array = []
            i = 0
            for d in data:
                #if i < 20:
                new_array.append(map('List Index [' + str(i) + '] ',d))
                i += 1
            return new_array

            
    def dict_from_firestore(self, data):

        def is_scalar_value(value):
            # It is possible that is key name is also a data type keyword.
            # If the value is scalar then the key is a data type.
            return not isinstance(value, dict) and not isinstance(value, list)
    
        def is_dict_value(value, keys):
            # It is possible that is key name is also a data type keyword.
            # If the value has expected structure then the key is a data type.
            if isinstance(value, dict) and len(value.keys()) == len(keys):
                for k in keys:
                    if k not in value:
                        return False
                return True
            return False
            
        new_dict = {}
        if isinstance(data, dict):
            for key in data:
                value = data[key]
                if is_scalar_value(value):
                    if key in ['nullValue']:
                        return None
                    elif key in ['stringValue']:
                        return str(value)
                    elif key in ['booleanValue']: 
                        return bool(value)
                    elif key in ['integerValue']:
                        return int(value)
                    elif key in ['doubleValue']:
                        return float(value)
                    elif key in ['bytesValue']:
                        return bytes(value.encode(errors='ignore'))
                    elif key in ['timestampValue']:   
                        return TimeStamp(str(value))
                    elif key in ['referenceValue']:
                        return Reference(str(value))
                elif key in ['mapValue'] and is_dict_value(value, ['fields']):
                    return self.dict_from_firestore(value['fields'])
                elif key in ['arrayValue'] and is_dict_value(value, ['values']):
                    array = []
                    for v in value['values']:
                        array.append(self.dict_from_firestore(v))
                    return array
                elif key in ['geoPointValue'] and\
                     is_dict_value(value, ['latitude', 'longitude']):
                    return GeoPoint(value['latitude'], value['longitude'])
                else:
                    new_dict[key] = self.dict_from_firestore(value)
        return new_dict

    ###############
    # Dict update
    ###############

    def dict_replace(self, existing, replace):
        tuples = False
        if isinstance(replace, dict) and isinstance(existing, dict):
            for key, value in replace.items():
                if key in existing:
                    if isinstance(value, dict):
                        self.dict_replace(existing[key], value)
                    elif isinstance(value, list):
                        if not self.dict_replace(existing[key], value):
                            existing[key] = value
                    else:
                        existing[key] = value
                else: # new key
                    existing[key] = value
        elif isinstance(replace, list) and isinstance(existing, list):
            for ele in replace:
                if isinstance(ele, tuple):
                    tuples = True
                    index = ele[0]
                    value = ele[1]
                    if index < len(existing):  
                        existing[index] = value
                    elif index == len(existing):
                        existing.append(value)
        return tuples
                
    def dict_pop(self, existing, removes):
        if isinstance(removes, dict) and isinstance(existing, dict):
            for key, value in removes.items():
                if key in existing:
                    if value and\
                       (isinstance(value, dict) or isinstance(value, list)): 
                        self.dict_pop(existing[key], value)
                    else:
                        existing.pop(key)
        elif isinstance(removes, list) and isinstance(existing, list):
            for ele in removes:   
                if not isinstance(ele, tuple):
                    return []
            descending = sorted(removes, key = lambda x: x[0], reverse = True)
            for ele in descending:  
                index = ele[0]
                value = ele[1]
                if value and\
                   (isinstance(value, dict) or isinstance(value, list)):
                    self.dict_pop(existing[index], value)
                elif index < len(existing):
                    existing.pop(index)
        return existing

    ###############
    # Utilities
    ###############

    def build_headers(self):
        assert self.id_token, 'Database not enabled.'
        return {'content-type' : 'application/json; charset=UTF-8',
                'Authorization' : 'Bearer ' + self.id_token}

    def dict_size(self, data):
        count = 0
        if isinstance(data, dict):
            for key in data.keys():
                count += self.dict_size(data[key])
        elif isinstance(data, list):
            for ele in data:
                count += self.dict_size(ele)
        else:
            count += 1
        return count
    
    def parse_result(self,r):
        if 'fields' in r:
            data = self.dict_from_firestore(r['fields'])
            if 'updateTime' in r:
                update_time = r['updateTime']
            else:
                update_time = ''
            return True, data, update_time
        elif 'error' in r and 'message' in r['error']:
            return False, 'ERROR: ' + r['error']['message'], ''
        else:
            return False, 'ERROR:' + str(r), ''
        
    def parse_result_update(self,r, data):
        if 'writeResults' in r and 'updateTime' in r['writeResults'][0]:
            update_time = r['writeResults'][0]['updateTime']
            return True, data, update_time
        elif 'error' in r and 'message' in r['error']:
            return False, 'ERROR: ' + r['error']['message'], ''
        else:
            return False, 'ERROR:' + str(r), ''
        
    
##########################################
# Classes for Firestore custom data types
##########################################
                
class GeoPoint:
    # Latitude in -90 to 90 , positive latitude is N.
    # Longtitude in -180 to 180 , positive longitude is E.
    # Conversion conventions:
    # Out of range values will be truncated to the poles or the antimeridian.
    # Every argument type except int and float default to equator or meridian.
    def __init__(self, latitude, longitude):
        if not isinstance(latitude, int) and not isinstance(latitude, float):
            latitude = 0
        if not isinstance(longitude, int) and not isinstance(longitude, float):
            longitude = 0
        self.dict = {'latitude' : min(max(latitude, -90), 90),
                     'longitude' : min(max(longitude, -180), 180)}

    def get(self):
        return self.dict
        
class TimeStamp:
    # value is a ISO 8601 string
    def __init__(self, value):
        self.datetime = "2000-01-01T00:00:00Z" # default last millenium
        if isinstance(value, str):
            self.datetime = value

    def get(self):
        return self.datetime

class Reference:
    # A document reference.
    # The value is a string specifing an existind document.
    # Format of the value is:
    # 'projects/{project}/databases/(default)/documents/{collection}/{document}
    def __init__(self, value):
        self.document = value

    def get(self):
        return self.document

