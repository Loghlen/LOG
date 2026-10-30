"""LOG's macOS Keychain item. Secrets never enter shell arguments or files."""
import ctypes as C
import json
import sys

SERVICE=b'LOG Local OpenAI'
ACCOUNT=b'connection'
NOT_FOUND=-25300
class StoreError(Exception): pass

def frameworks():
    if sys.platform!='darwin': raise StoreError('Saving the connection requires macOS Keychain.')
    sec=C.CDLL('/System/Library/Frameworks/Security.framework/Security')
    cf=C.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
    ptr=C.c_void_p;uint=C.c_uint32
    signatures={
      'SecKeychainFindGenericPassword':[ptr,uint,C.c_char_p,uint,C.c_char_p,C.POINTER(uint),C.POINTER(ptr),C.POINTER(ptr)],
      'SecKeychainAddGenericPassword':[ptr,uint,C.c_char_p,uint,C.c_char_p,uint,ptr,C.POINTER(ptr)],
      'SecKeychainItemModifyAttributesAndData':[ptr,ptr,uint,ptr],
      'SecKeychainItemFreeContent':[ptr,ptr],
      'SecKeychainItemDelete':[ptr],
    }
    for name,args in signatures.items():
        fn=getattr(sec,name);fn.argtypes=args;fn.restype=C.c_int32
    cf.CFRelease.argtypes=[ptr];cf.CFRelease.restype=None
    return sec,cf

def check(code):
    if code: raise StoreError('macOS Keychain could not complete the request (code %s). Unlock your login Keychain and allow LOG access, then try again.'%code)

def find(sec):
    length=C.c_uint32();data=C.c_void_p();item=C.c_void_p()
    code=sec.SecKeychainFindGenericPassword(None,len(SERVICE),SERVICE,len(ACCOUNT),ACCOUNT,C.byref(length),C.byref(data),C.byref(item))
    return code,length,data,item

def read():
    sec,cf=frameworks();code,length,data,item=find(sec)
    if code==NOT_FOUND:return None
    check(code)
    try:
        value=json.loads(C.string_at(data,length.value).decode())
        if not isinstance(value,dict) or not isinstance(value.get('key'),str) or not isinstance(value.get('model'),str):raise ValueError()
        return value
    except (ValueError,UnicodeError):raise StoreError('The saved LOG connection is unreadable. Reconnect to replace it.') from None
    finally:
        sec.SecKeychainItemFreeContent(None,data)
        if item:cf.CFRelease(item)

def write(key,model):
    sec,cf=frameworks();value=json.dumps({'key':key,'model':model}).encode()
    buffer=C.create_string_buffer(value)
    code,length,data,item=find(sec)
    if code==NOT_FOUND:
        check(sec.SecKeychainAddGenericPassword(None,len(SERVICE),SERVICE,len(ACCOUNT),ACCOUNT,len(value),buffer,None))
        return
    check(code)
    try:check(sec.SecKeychainItemModifyAttributesAndData(item,None,len(value),buffer))
    finally:
        sec.SecKeychainItemFreeContent(None,data)
        if item:cf.CFRelease(item)

def delete():
    sec,cf=frameworks();code,length,data,item=find(sec)
    if code==NOT_FOUND:return
    check(code)
    try:check(sec.SecKeychainItemDelete(item))
    finally:
        sec.SecKeychainItemFreeContent(None,data)
        if item:cf.CFRelease(item)
