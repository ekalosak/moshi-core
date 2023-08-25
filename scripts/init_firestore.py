"""This script initializes the Firestore database with the following collections:
- `transcripts`
- `profiles`
- `config`
- `news`

First it creates the config collection:
- document ID is `supported_langs`:
    - it has 1 element: `lang`: array of strings e.g. `["en-US", "es-MX", ...]` use 20 most popular languages

Second, it creates a default user in Firebase Auth with the following credentials:
- email: `test@test.test`
- password: `testtest`

Third, it creates a default profile for the default user with the following attributes:
- document ID is user uid
- `lang`: `en-US`
- `primary_lang`: `en-US`
- `name`: `Timmy Test`

Fourth, it creates a doc in the info collection:
- `type`: `privacy_policy`
- `body`: `...`
"""

import os
from sys import exit
from datetime import datetime

import firebase_admin
import google.cloud.firestore as firestore
from firebase_admin import auth
from firebase_admin import credentials
from firebase_admin import firestore

PROJECT_ID = "moshi-3"
COLLECTIONS = ["transcripts", "profiles", "config", "moshinews"]
DEFAULT_USER_EMAIL = "test@test.test"
DEFAULT_USER_PASSWORD = "testtest"
DEFAULT_USER_NAME = "Timmy Test"
DEFAULT_USER_LANG = "en-US"
DEFAULT_USER_PRIMARY_LANG = "en-US"

envvars = ["FIRESTORE_EMULATOR_HOST", "FIREBASE_AUTH_EMULATOR_HOST"]
missing = []
for envvar in envvars:
    val = os.getenv(envvar)
    print(f"Found {envvar}={val}")
    if not val:
        missing.append(envvar)
if missing:
    # confirm with user
    print(f"Missing environment variables: {missing}")
    print("🧯 Without these variables, this script will use the production database for the current gcloud project.")
    ok = input("Continue? [y/N] ")
    if ok.lower() != "y":
        exit(1)

SUPPORTED_LANGS = [
    "en-US",
    "es-MX",
    "es-ES",
    "fr-FR",
    "fr-CA",
    "de-DE",
    "it-IT",
    "ja-JP",
    "ko-KR",
    "cmn-CN",
    "cmn-HK",
    "cmn-TW",
]

def _init_firestore():
    """Initialize the Firestore database."""
    db = firestore.client()
    return db

def _init_auth():
    """Initialize the Firebase Auth client."""
    # use the application default credentials
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred, {
        'projectId': PROJECT_ID,
    })
    print("Successfully initialized the Firebase Admin SDK.")
    return auth

def _init_config(db):
    """Initialize the config collection."""
    doc_ref = db.collection("config").document("supported_langs")
    doc_ref.set({"langs": SUPPORTED_LANGS})
    print("Successfully initialized the config collection.")

def _init_info(db):
    """Initialize the moshinews collection."""
    doc_ref = db.collection("info").document()
    doc_ref.set({
        "title": "Terms of Service",
        "subtitle": "Last updated: 2023-08-12",
        "body": "This is the β version of Moshi. We are still working out the kinks, so please be patient with us. Here are the things you need to know:\n\n - We may update these terms of service at any time.\n\n - Moshi is currently free, with limits.\n\n - Please do not use Moshi for anything sensitive or confidential.\n\n - If you voilate our internal content moderation policies, we may ban you without notice.\n\n - Please read the privacy policy for more information about what we do with your data.",
        "type": "policy",
        "timestamp": datetime.now(),
    })
    doc_ref = db.collection("info").document()
    doc_ref.set({
        "title": "Privacy Policy",
        "subtitle": "Last updated: 2023-08-09",
        "body": "The Moshi team takes your privacy seriously.\n\nAny data we do collect is encrypted at rest and in flight.  We only share conversational content with you and select 3rd party API providers required to operate this service.  We use best effort to ensure our API vendors adhere to high privacy standards.\n\nWe do not sell your data as a product.  We do not currently use your data for advertising purposes, but may do so in the future in de-identified aggregate.  We do use your data to improve our service.\n\nWe do not currently have a way for you to delete your data in the App, but we will happily do so upon request via the Feedback page.  We do not store audio recordings, but we do store transcripts of the conversations you have with Moshi.  These transcripts are available to you on the Transcripts page.\n\nWe do not knowingly collect data from children under 13.  If you are a parent or guardian and believe we have collected data from your child, please use the Feedback page to contact us - we will remove it immediately.\n\nWe may update this privacy policy at any time.  When we update it, the date on this message will update accordingly.  For major changes, we will notify you in a highlighted message on this feed.\n\nThank you for taking the time to consider how we use your data.  We hope you enjoy using Moshi!",
        "type": "policy",
        "timestamp": datetime.now(),
        })
    # doc_ref = db.collection("info").document()
    # doc_ref.set({
    #     "title": "Updates",
    #     "subtitle": "We'll post updates here as we make them.",
    #     "body": "Please visit www.chatmoshi.com for the latest on the Moshi app.",
    #     "type": "update",
    #     "timestamp": datetime.now(),
    # })
    doc_ref = db.collection("info").document()
    doc_ref.set({
        "title": "Moshi Beta is live!",
        "subtitle": "Thank you for giving Moshi a try!",
        "body": "The Moshi β is now live! Thank you for your patience as we continue to improve the service. To get started, click the 'Chat' button.",
        "type": "news",
        "timestamp": datetime.now(),
    })
    print("Successfully initialized the info collection.")

def _init_feed(db):
    """Initialize the user feed collection."""
    doc_ref = db.collection("feed").document()
    doc_ref.set({
        "uid": "test",
        "title": "Test feed message",
        "subtitle": "This is a test feed message.",
        "body": "This is a test feed message.",
        "timestamp": datetime.now(),
        "type": "test",
    })
    print("Successfully initialized the feed collection.")

def _init_feedback(db):
    """Initialize the feedback collection."""
    doc_ref = db.collection("feedback").document()
    doc_ref.set({
        "uid": "test",
        "body": "This is a test feedback message.",
        "timestamp": datetime.now(),
        "type": "test",
    })
    print("Successfully initialized the feedback collection.")

def _init_profile(db, uid):
    """Initialize the profiles collection."""
    doc_ref = db.collection("profiles").document(uid)
    doc_ref.set({
        "lang": DEFAULT_USER_LANG,
        "primary_lang": DEFAULT_USER_PRIMARY_LANG,
        "name": DEFAULT_USER_NAME,
    })
    print("Successfully initialized the profiles collection.")

def _init_user(auth):
    """Initialize the default user."""
    try:
        user = auth.create_user(
            uid="test",
            email=DEFAULT_USER_EMAIL,
            password=DEFAULT_USER_PASSWORD,
            display_name=DEFAULT_USER_NAME,
        )
    except firebase_admin._auth_utils.EmailAlreadyExistsError:
        print("User already exists.")
        user = auth.get_user_by_email(DEFAULT_USER_EMAIL)
    else:
        print('Successfully created new user.')
    print("\tDefault user: ",  user.email, user.display_name)
    return user.uid

def main():
    """Initialize the Firestore database."""
    auth = _init_auth()
    # uid = _init_user(auth)
    uid = "gaybRfuMyvXtAz5eK5mdgxqD9wv1"
    db = _init_firestore()
    _init_profile(db, uid)
    _init_config(db)
    _init_info(db)
    _init_feed(db)
    _init_feedback(db)

if __name__ == "__main__":
    print("START")
    main()
    print("END")
