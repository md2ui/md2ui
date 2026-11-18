<!--Source LLM generated-->
# API Reference

[`✨ Ask about this section`](agent:ask-about-section?section=api-reference) | [`📋 Copy for LLM`](agent:copy-for-llm?section=api-reference) | [`📄 View as Markdown`](/api.md)

The Parcel API follows [REST](https://example.com/rest) conventions. It has predictable, resource-shaped URLs, takes [form-encoded](https://example.com/form-encoding) request bodies, answers with [JSON](https://example.com/json) responses, and uses ordinary HTTP status codes, authentication and verbs.

You can call the Parcel API in [sandboxes](/sandboxes) without printing real labels or booking real couriers. The API key that [authenticates](/api/authentication) a request decides whether it runs live or in a sandbox. Sandboxes support every v2 endpoint. Older test sandboxes support some [v2 endpoints](/testing#compare).

The Parcel API has no bulk updates. Each request changes one object.

The Parcel API varies by account as we ship new [versions](/api/versioning) and features. [Sign in](https://console.parcel.example/login?next=%2Fapi) to see these pages with your own test key and data.

_Was this section helpful?_ - **[Yes](agent:helpful?section=api-reference&answer=yes)** **[No](agent:helpful?section=api-reference&answer=no)**

## Just getting started?

Follow the [first shipment](/get-started/first-shipment) guide.

___

## Not a developer?

Use Parcel’s [no-code tools](/no-code) or apps from [our partners](https://partners.parcel.example/) to start shipping with Parcel and do more with your account—no code needed.
***

#### BASE URL ... [📋](agent:copy?block=base-url) [✨](agent:ask?block=base-url)

```text
https://api.parcel.example
```
***

#### CLIENT LIBRARIES

___
... ![Ruby](https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/ruby/ruby-plain.svg?md2ui.max_width=24&md2ui.aspect_ratio=1:1) ...
... Ruby ...
:::
... ![Python](https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/python/python-original.svg?md2ui.max_width=24&md2ui.aspect_ratio=1:1) ...
... Python ...
:::
... ![PHP](https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/php/php-original.svg?md2ui.max_width=24&md2ui.aspect_ratio=1:1) ...
... PHP ...
:::
... ![Java](https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/java/java-original.svg?md2ui.max_width=24&md2ui.aspect_ratio=1:1) ...
... Java ...
:::
... ![Node.js](https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/nodejs/nodejs-original.svg?md2ui.max_width=24&md2ui.aspect_ratio=1:1) ...
... Node.js ...
:::
... ![Go](https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/go/go-original-wordmark.svg?md2ui.max_width=24&md2ui.aspect_ratio=1:1) ...
... Go ...
:::
... ![.NET](https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/dot-net/dot-net-plain.svg?md2ui.max_width=24&md2ui.aspect_ratio=1:1) ...
... .NET ...
___

---

___
```console
$ gem install parcel-api
```
:::
... [🐙 PARCEL-RUBY](https://code.example.com/parcel/parcel-ruby)
:::0
___
***
***
___

# Authentication

[`✨ Ask about this section`](agent:ask-about-section?section=authentication) | [`📋 Copy for LLM`](agent:copy-for-llm?section=authentication) | [`📄 View as Markdown`](/api/authentication.md)

The Parcel API authenticates requests with [API keys](/keys). You can see and rotate your keys in [the Parcel Console](https://console.parcel.example/login?next=/keys).

Test secret keys start with `pk_test_` and live secret keys start with `pk_live_`. You can also use [scoped API keys](/keys#scopes) for narrower permissions.

Your API keys can do a great deal. Follow [the key guide](/keys-guide) to keep them safe. Never put a secret (or scoped) key in source code or in an app that runs on a customer’s device. Store keys in your server’s secrets manager and read them at runtime. If your host has no secrets manager, keep the keys in environment variables.

Pass your API key when you create a [ParcelClient](/api/parcel-client). The Ruby library then sends that key with every request.

You can also pass a key for a single request. This helps marketplace apps that hold several API keys during one process. Methods on the object it returns keep using that key.

Send every API request over [HTTPS](https://example.com/https). Calls over plain HTTP fail, and so do calls without authentication.

_Was this section helpful?_ - **[Yes](agent:helpful?section=authentication&answer=yes)** **[No](agent:helpful?section=authentication&answer=no)**

#### INITIALIZE PARCELCLIENT ... *[Ruby ↕](agent:choose-language?block=initialize-client)* [📋](agent:copy?block=initialize-client) [✨](agent:ask?block=initialize-client)

```ruby
require 'parcel'
# A test key; keep live keys out of code. See https://docs.parcel.example/keys-guide.
client = Parcel::Client.new("pk_test_7Hq2Lx...v91ZpK4m")
```

#### PER-REQUEST API KEY ... *[Ruby ↕](agent:choose-language?block=per-request-key)* [📋](agent:copy?block=per-request-key) [✨](agent:ask?block=per-request-key)

```ruby
shipment = client.v1.shipments.retrieve(
  'shp_9KdQ2mWvT4xN8bR1cL0a',
  {},
  {
    api_key: 'pk_test_7Hq2Lx...v91ZpK4m'
  }
)
shipment.buy_label() # Uses the same per-request API key.
```

#### YOUR API KEY

Every example on this page already holds your test secret key, so you can run any of them now. Nobody else sees this value.
***
***
___

# Errors

[`✨ Ask about this section`](agent:ask-about-section?section=errors) | [`📋 Copy for LLM`](agent:copy-for-llm?section=errors) | [`📄 View as Markdown`](/api/errors.md)

Parcel answers with ordinary HTTP status codes to say whether a request worked. In short\: Codes in the `2xx` range mean success. Codes in the `4xx` range mean the request could not be done with what it sent (e.g., a required parameter was missing, an address could not be verified, etc.). Codes in the `5xx` range mean something failed on Parcel’s side (these are rare).

Some `4xx` errors your code can handle on its own (e.g., an address is [undeliverable](/addresses)) carry an [error code](/error-codes) that names the problem briefly.

_Was this section helpful?_ - **[Yes](agent:helpful?section=errors&answer=yes)** **[No](agent:helpful?section=errors&answer=no)**

### Attributes

---

***`code`*** - _nullable string_
For errors your code can handle, a short string naming the [error code](/error-codes).

---

***`carrier_code`*** - _nullable string_
For label errors a courier rejected, a short string giving the [courier’s reason](/carriers#rejections) when it sends one.

---

***`message`*** - _nullable string_
A readable message with more detail about the error. For address errors, you can show it to your customers.

---

***`param`*** - _nullable string_
When the error concerns one parameter, the name of that parameter. You can use it to show the message beside the right form field.

---

***`shipment`*** - _nullable hash_
The [Shipment object](/api/shipments/object) for errors returned on a request that involves a shipment.

---

***`type`*** - _enum_
The kind of error returned. One of `api_error`, `address_error`, `idempotency_error`, or `invalid_request_error`

| Possible enum values |
| --- |
| `api_error` |
| `address_error` |
| `idempotency_error` |
| `invalid_request_error` |

### More ... [`Expand all`](agent:expand-all?section=errors)

- ***`advice_code`*** - _nullable string_
- ---
- ***`label`*** - _nullable string_
- ---
- ***`doc_url`*** - _nullable string_
- ---
- ***`carrier_advice_code`*** - _nullable string_
- ---
- ***`carrier_reject_code`*** - _nullable string_
- ---
- ***`rate`*** - _nullable hash_
- ---
- ***`rate_service_level`*** - _nullable string_
- ---
- ***`request_log_url`*** - _nullable string_
- ---
- ***`pickup`*** - _nullable hash_
- ---
- ***`return_label`*** - _nullable hash_
***

#### HTTP STATUS CODE SUMMARY

| | | |
| --- | --- | --- |
| **200** | OK | The request worked. |
| **400** | Bad Request | The request could not be accepted, often because a required parameter is missing. |
| **401** | Unauthorized | No valid API key was sent. |
| **402** | Request Failed | The parameters were valid, but the request still failed. |
| **403** | Forbidden | The API key is not allowed to make this request. |
| **404** | Not Found | The requested object does not exist. |
| **409** | Conflict | The request clashes with another one (perhaps it reused an idempotency key). |
| **424** | External Dependency Failed | The request could not finish because a courier or other outside service failed. |
| **429** | Too Many Requests | Too many requests arrived too quickly. Back off exponentially and retry. |
| **500, 502, 503, 504** | Server Errors | Something broke on Parcel’s side. (These are rare.) |

#### ERROR TYPES

| | |
| --- | --- |
| `api_error` | API errors cover every other kind of problem (e.g., a brief outage on Parcel’s side), and are very rare. |
| `address_error` | Address errors are the ones you will handle most often. They happen when a customer enters an address that couldn’t be verified for some reason. |
| `idempotency_error` | Idempotency errors happen when an `Idempotency-Key` is reused on a request whose endpoint and parameters differ from the first one. |
| `invalid_request_error` | Invalid request errors happen when a request carries invalid parameters. |
***
***
___

# Handling errors

[`✨ Ask about this section`](agent:ask-about-section?section=handling-errors) | [`📋 Copy for LLM`](agent:copy-for-llm?section=handling-errors) | [`📄 View as Markdown`](/api/errors/handling.md)

The client libraries raise exceptions for many reasons, such as a rejected label, invalid parameters, authentication errors and network outages. Write code that handles every API exception cleanly.

Related guide: [Handling errors](/handling-errors)

#### ... *[Ruby ↕](agent:choose-language?block=handling-errors)* [📋](agent:copy?block=handling-errors) [✨](agent:ask?block=handling-errors)

```ruby
begin
  # Use the Parcel library to make requests...
rescue Parcel::AddressError => e
  # An address that could not be verified
  puts "Status: #{e.http_status}"
  puts "Type: #{e.error.type}"
  puts "Code: #{e.error.code}" if e.error.code
  puts "Carrier code: #{e.error.carrier_code}" if e.error.carrier_code
  puts "Param: #{e.error.param}" if e.error.param
  puts "Message: #{e.error.message}"
  puts "Request ID: #{e.request_id}"
rescue Parcel::RateLimitError => e
  # Too many requests reached the API too quickly
  puts "Request ID: #{e.request_id}"
rescue Parcel::InvalidRequestError => e
  # The request carried invalid parameters
  puts "Request ID: #{e.request_id}"
rescue Parcel::AuthenticationError => e
  # Authenticating with the Parcel API failed
  # (perhaps the API keys were rotated)
  puts "Request ID: #{e.request_id}"
rescue Parcel::APIConnectionError => e
  # The network connection to Parcel failed
  puts "Request ID: #{e.request_id}"
rescue Parcel::ParcelError => e
  # Show a general error to the user, and perhaps
  # send yourself an alert
  puts "Request ID: #{e.request_id}"
rescue => e
  # Something else went wrong, unrelated to Parcel
end
```
***
***
___

# Expanding Responses

[`✨ Ask about this section`](agent:ask-about-section?section=expanding) | [`📋 Copy for LLM`](agent:copy-for-llm?section=expanding) | [`📄 View as Markdown`](/api/expanding_objects.md)

Many objects can return extra detail as an expanded response through the `expand` request parameter. Every API request accepts it, and it applies only to that request’s response. There are two ways to expand.

Often an object holds the ID of a related object among its properties. For example, a `Shipment` might hold a Customer ID. You can expand those objects in place with the expand parameter. The `expandable` label on these pages marks the ID fields you can expand into objects.

Some fields are left out of responses by default, such as the `barcode` and `pin` fields on the Locker object. You can ask for them as an expanded response with the `expand` request parameter.

You can expand recursively by naming nested fields after a dot (`.`). For example, asking for `rate.carrier` on a shipment expands the `rate` property into a full Rate object, then expands the `carrier` property on that rate into a full Carrier object.

The `expand` parameter works on any endpoint that returns expandable fields, including list, create and update endpoints.

Expansions on list requests begin with the `data` property. For example, you can expand `data.customers` on a request that lists shipments and their customers. Deep expansions on many list requests can slow responses down.

Expansions go at most four levels deep (for example, the deepest expansion allowed when listing shipments is `data.rate.carrier.default_service`).

You can expand several objects at once by listing them in the `expand` array.

- Related guide: [Expanding responses](/expand)
- Related video: [Expand](https://video.example.com/watch?v=expand-101)

_Was this section helpful?_ - **[Yes](agent:helpful?section=expanding&answer=yes)** **[No](agent:helpful?section=expanding&answer=no)**
