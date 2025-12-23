DOMAIN = "tada"

COGNITO_URL = "https://cognito-idp.eu-west-1.amazonaws.com/"
DEFAULT_CLIENT_ID = "315bgoo27jq3bhr1aicgcl43t1"

WS_URL = "wss://83hcyphgea.execute-api.eu-west-1.amazonaws.com/prod/"

TIMEOUT = 10
UPDATE_INTERVAL_MINUTES = 5

# Per-period update intervals (in minutes)
# - Today/general entities: frequent updates
# - Yesterday-specific entities: hourly updates
# - Other historical/custom periods: daily updates
UPDATE_INTERVAL_TODAY_MINUTES = 5
UPDATE_INTERVAL_YESTERDAY_MINUTES = 60
UPDATE_INTERVAL_DAILY = 24 * 60

# Common device names and suffixes used across entities
DEVICE_NAME_BASE = "Tada"
DEVICE_NAME_TODAY = "Tada Today"
DEVICE_NAME_YESTERDAY = "Tada Yesterday"

DEVICE_SUFFIX_BASE = "base"
DEVICE_SUFFIX_TODAY = "today"
DEVICE_SUFFIX_YESTERDAY = "yesterday"
