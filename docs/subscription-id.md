# Retrieve your Subscription ID

You can obtain `subscription_id` by inspecting network API calls in the Tada web application. It is present in many API calls on the page:

Page: https://webapp.tada.magie-tada.com/it/la-tua-casa

## Steps (Chrome/Edge/Firefox)
1. Log in to the Tada web app and navigate to "La tua casa".
2. Open Developer Tools:
   - Chrome/Edge: press `F12` or `Ctrl+Shift+I`.
   - Firefox: press `F12` or `Ctrl+Shift+I`.
3. Go to the "Network" tab.
   - Enable "Preserve log" if available.
   - Filter by "Fetch/XHR" requests to see API calls.
4. Reload the page or interact with the dashboard so calls appear.
5. Click any XHR/API request listed and inspect:
   - Headers → URL/query string: look for `subscription_id`.
   - Payload/Request body (if present): look for `subscription_id`.
   - Response (if easier): some endpoints echo `subscription_id`.
6. Copy the exact `subscription_id` value and paste it into the integration configuration in Home Assistant.

### Tips
- Multiple API calls will contain `subscription_id`; any matching value is fine.
- If you don’t see API calls, ensure you’re on "La tua casa", then reload.
