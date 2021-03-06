#!/usr/bin/python
# -*- coding: utf-8 -*-
import re
import string
import pycrfsuite
import os
import warnings
from collections import OrderedDict


#  _____________________
# |1. CONFIGURE LABELS! |
# |_____________________| 
#     (\__/) || 
#     (•ㅅ•) || 
#     / 　 づ
LABELS = ['AddressNumber',
            'StreetName',
            'CityName',
            'StateName',
            'RegionName',
            'ZipCode',
            'CountryName',
            'AddressNumberPrefix',
            'AddressNumberSuffix',
            'StreetNamePreDirectional',
            'StreetNamePostDirectional',
            'StreetNamePreModifier',
            'StreetNamePostType',
            'StreetNamePreType',
            'USPSBoxType',
            'USPSBoxID',
            'USPSBoxGroupType',
            'USPSBoxGroupID',
            'LandmarkName',
            'OccupancyType',
            'OccupancyIdentifier',
            'SubaddressIdentifier',
            'SubaddressType',
            'Recipient',
            'BuildingName',
            'NotAddress'] # The labels should be a list of strings

#***************** OPTIONAL CONFIG ***************************************************
PARENT_LABEL  = 'TokenSequence'               # the XML tag for each labeled string
GROUP_LABEL   = 'Collection'                  # the XML tag for a group of strings
NULL_LABEL    = 'Null'                        # the null XML tag
MODEL_FILE    = 'intaddress.crfsuite'   # filename for the crfsuite settings file
#************************************************************************************


try :
    TAGGER = pycrfsuite.Tagger()
    TAGGER.open(os.path.split(os.path.abspath(__file__))[0]+'/'+MODEL_FILE)
except IOError :
    TAGGER = None
    warnings.warn('You must train the model (parserator train [traindata] [modulename]) to create the %s file before you can use the parse and tag methods' %MODEL_FILE)

def parse(raw_string):
    if not TAGGER:
        raise IOError('\nMISSING MODEL FILE: %s\nYou must train the model before you can use the parse and tag methods\nTo train the model annd create the model file, run:\nparserator train [traindata] [modulename]' %MODEL_FILE)

    tokens = tokenize(raw_string)
    if not tokens :
        return []

    features = tokens2features(tokens)

    tags = TAGGER.tag(features)
    return zip(tokens, tags)

def tag(raw_string) :
    tagged = OrderedDict()
    for token, label in parse(raw_string) :
        tagged.setdefault(label, []).append(token)

    for token in tagged :
        component = ' '.join(tagged[token])
        component = component.strip(' ,;')
        tagged[token] = component

    return tagged


#  _____________________
# |2. CONFIGURE TOKENS! |
# |_____________________| 
#     (\__/) || 
#     (•ㅅ•) || 
#     / 　 づ
def tokenize(raw_string):
    # this determines how any given string is split into its tokens
    # handle any punctuation you want to split on, as well as any punctuation to capture
    
    if isinstance(raw_string, bytes):
        address_string = str(raw_string, encoding='utf-8')
    address_string = re.sub('(&#38;)|(&amp;)', '&', raw_string)
    re_tokens = re.compile(r"""
    \(*\b[^\s,;#&()]+[.,;)\n]*   # ['ab. cd,ef '] -> ['ab.', 'cd,', 'ef']
    |
    [#&]                       # [^'#abc'] -> ['#']
    """,
                           re.VERBOSE | re.UNICODE)

    tokens = re_tokens.findall(address_string)

    if not tokens:
        return []

    return tokens


#  _______________________
# |3. CONFIGURE FEATURES! |
# |_______________________| 
#     (\__/) || 
#     (•ㅅ•) || 
#     / 　 づ
def tokens2features(tokens):
    # this should call tokenFeatures to get features for individual tokens,
    # as well as define any features that are dependent upon tokens before/after
    
    feature_sequence = [tokenFeatures(tokens[0])]
    previous_features = feature_sequence[-1].copy()

    for token in tokens[1:] :
        # set features for individual tokens (calling tokenFeatures)
        token_features = tokenFeatures(token)
        current_features = token_features.copy()

        # features for the features of adjacent tokens
        feature_sequence[-1]['next'] = current_features
        token_features['previous'] = previous_features        
        
        # DEFINE ANY OTHER FEATURES THAT ARE DEPENDENT UPON TOKENS BEFORE/AFTER
        # for example, a feature for whether a certain character has appeared previously in the token sequence
        
        feature_sequence.append(token_features)
        previous_features = current_features

    if len(feature_sequence) > 1 :
        # these are features for the tokens at the beginning and end of a string
        feature_sequence[0]['rawstring.start'] = True
        feature_sequence[-1]['rawstring.end'] = True
        feature_sequence[1]['previous']['rawstring.start'] = True
        feature_sequence[-2]['next']['rawstring.end'] = True

    else : 
        # a singleton feature, for if there is only one token in a string
        feature_sequence[0]['singleton'] = True

    return feature_sequence

def tokenFeatures(token) :
    # this defines a dict of features for an individual token
    if token in (u'&', u'#', u'½'):
        token_clean = token
    else:
        token_clean = re.sub(r'(^[\W]*)|([^.\w]*$)', u'', token)

    token_abbrev = re.sub(r'[.]', u'', token_clean.lower())
    features = {'abbrev': token_clean[-1] == u'.',
                'digits': digits(token_clean),
                'word': (token_abbrev
                         if not token_abbrev.isdigit()
                         else False),
                'trailing.zeros': (trailingZeros(token_abbrev)
                                   if token_abbrev.isdigit()
                                   else False),
                'length': (u'd:' + str(len(token_abbrev))
                           if token_abbrev.isdigit()
                           else u'w:' + str(len(token_abbrev))),
                'endsinpunc': (token[-1]
                               if bool(re.match('.+[^.\w]', token))
                               else False),
                'has.vowels': bool(set(token_abbrev[1:]) & set('aeiou')),
                }

    return features

def digits(token):
    if token.isdigit():
        return 'all_digits'
    elif set(token) & set(string.digits):
        return 'some_digits'
    else:
        return 'no_digits'


def trailingZeros(token):
    results = re.findall(r'(0+)$', token)
    if results:
        return results[0]
    else:
        return ''

class RepeatedLabelError(Exception):
    def __init__(self, original_string, parsed_string, repeated_label):
        message = '''
ERROR: Unable to tag this string because more than one area of the string has the same label
ORIGINAL STRING:  %s
PARSED TOKENS:    %s
UNCERTAIN LABEL:  %s
When this error is raised, it's likely that either (1) the string is not a valid address or (2) some tokens were labeled incorrectly
To report an error in labeling a valid address, open an issue at https://github.com/datamade/usaddress/issues/new - it'll help us continue to improve usaddress!
For more information, see the documentation at http://usaddress.readthedocs.org/
        ''' % (original_string, parsed_string, repeated_label)

        super(RepeatedLabelError, self).__init__(message)

        self.original_string = original_string
        self.parsed_string = parsed_string