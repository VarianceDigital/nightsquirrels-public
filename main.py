from nightsquirrel import create_app
import os

os.environ["SESSION_SECRET"]="YourSessionSecret"
os.environ["JWT_SECRET_HTML"]="YourHTMLApiSecret"
os.environ["JWT_MAILER_SECRET"]="YourMailerSecret"
os.environ["MAILER_URL"]="https://mymailer.sass.com/"
os.environ["AWS_TILES_BUCKET_NAME"]="my-tiles" #for user tiles
os.environ["AWS_TILES_BUCKET_URL"]="https://my-tiles.s3.eu-west-3.amazonaws.com/"
os.environ["AWS_DOCS_BUCKET_NAME"]="my-documents" #for question documents
os.environ["AWS_DOCS_BUCKET_URL"]="https://my-documents.s3.eu-west-3.amazonaws.com/"
os.environ["AWS_REF_IMAGES_BUCKET_NAME"]="nightsquirrel-reference-images" #for reference cover/thumbnail images
os.environ["AWS_REF_IMAGES_BUCKET_URL"]="https://nightsquirrel-reference-images.s3.eu-west-3.amazonaws.com/"
os.environ["AWS_ACCESS_KEY"]="YOURAWSACCESSKEY"
os.environ["AWS_SECRET_ACCESS_KEY"]="LongerAWSAccessSecret"
os.environ["PAYPAL_CLIENT_ID"]="YourPayPalClientId"
os.environ["PAYPAL_CLIENT_SECRET"]="YourPayPalClientSecret"
os.environ["PAYPAL_MODE"]="sandbox"
os.environ["ADMIN_EMAIL"]="admin@example.com"
os.environ["BASE_URL"]="http://127.0.0.1:5000"
os.environ["PUSHER_APP_ID"]="YourPusherAppId"
os.environ["PUSHER_KEY"]="YourPusherKey"
os.environ["PUSHER_SECRET"]="YourPusherSecret"
os.environ["PUSHER_CLUSTER"]="eu"
os.environ["ANTHROPIC_API_KEY"]="YourAnthropicApiKey"
os.environ["GOOGLE_BOOKS_API_KEY"]="YourGoogleBookApiKey"

app = create_app()
app.run()

