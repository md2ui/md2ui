# API Reference

[`✨ Ask about this section`](agent:ask-about-section?section=api-reference) | [`📋 Copy for LLM`](agent:copy-for-llm?section=api-reference) | [`📄 View as Markdown`](/api.md)

The Plinth API is built on [REST](https://example.com/rest) principles. Its URLs name resources in a predictable way, it accepts [form-encoded](https://example.com/form-encoding) request bodies, returns [JSON](https://example.com/json) responses, and relies on standard HTTP verbs, status codes and authentication.

You can try the Plinth API in [test workspaces](/test-workspaces) without holding real venues or charging real deposits. Which API key [authenticates](/api/authentication) a request decides whether it runs live or in a test workspace. Test workspaces cover every v3 endpoint. The older sandbox mode covers only some [v3 endpoints](/testing#compare).

The Plinth API does not offer batch writes. Every request acts on a single object.

The Plinth API can differ from one account to the next as we release new [versions](/api/versioning) and features. [Sign in](https://console.example.com/login?next=%2Fapi) to read these pages with your own test key and data filled in.

_Was this section helpful?_ - **[Yes](agent:helpful?section=api-reference&answer=yes)** **[No](agent:helpful?section=api-reference&answer=no)**

## New to Plinth?

Start with the [first booking](/get-started/first-booking) guide.

___

## Not writing code?

Try Plinth’s [no-code dashboard](/no-code) or a tool from [our app directory](https://apps.example.com/) to start taking bookings with Plinth and get more from your account—no programming required.
***

#### BASE URL ... [📋](agent:copy?block=base-url) [✨](agent:ask?block=base-url)

```text
https://api.example.com
```
***

#### CLIENT LIBRARIES

___
... ![Ruby](https://example.com/icons/ruby.svg?md2ui.max_width=24&md2ui.aspect_ratio=1:1) ...
... Ruby ...
:::
... ![Python](https://example.com/icons/python.svg?md2ui.max_width=24&md2ui.aspect_ratio=1:1) ...
... Python ...
:::
... ![PHP](https://example.com/icons/php.svg?md2ui.max_width=24&md2ui.aspect_ratio=1:1) ...
... PHP ...
:::
... ![Java](https://example.com/icons/java.svg?md2ui.max_width=24&md2ui.aspect_ratio=1:1) ...
... Java ...
:::
... ![Node.js](https://example.com/icons/nodejs.svg?md2ui.max_width=24&md2ui.aspect_ratio=1:1) ...
... Node.js ...
:::
... ![Go](https://example.com/icons/go.svg?md2ui.max_width=24&md2ui.aspect_ratio=1:1) ...
... Go ...
:::
... ![.NET](https://example.com/icons/dotnet.svg?md2ui.max_width=24&md2ui.aspect_ratio=1:1) ...
... .NET ...
___

---

___
```console
$ gem install plinth-sdk
```
:::
... [🐙 PLINTH-RUBY](https://code.example.com/plinth/plinth-ruby)
:::0
___
***
***
___

# Authentication

[`✨ Ask about this section`](agent:ask-about-section?section=authentication) | [`📋 Copy for LLM`](agent:copy-for-llm?section=authentication) | [`📄 View as Markdown`](/api/authentication.md)

Every Plinth API request is authenticated with an [API key](/keys). You can view, create and roll your keys in [the Plinth dashboard](https://console.example.com/login?next=/keys).

Test secret keys begin with `vk_test_` and live secret keys begin with `vk_live_`. For tighter access, create [restricted keys](/keys#restricted) that can reach only some resources.

An API key carries real power over your account. Read [the key safety guide](/keys-safety) before you ship. Keep secret and restricted keys out of source control and out of any app that runs on a guest’s phone or browser. Load them at runtime from your platform’s secrets store. Where no secrets store exists, put them in environment variables.

Give your API key to the [PlinthClient](/api/plinth-client) when you construct it. From then on, the Ruby library attaches that key to every call.

A key can also be set on one request alone. That suits booking platforms that act for many venues and hold a key for each one in the same process. Any method you call on the returned object goes on using that key.

Make every API call over [HTTPS](https://example.com/https). Requests over plain HTTP are refused, as are requests with no authentication.

_Was this section helpful?_ - **[Yes](agent:helpful?section=authentication&answer=yes)** **[No](agent:helpful?section=authentication&answer=no)**

#### CREATE A PLINTHCLIENT ... *[Ruby ↕](agent:choose-language?block=create-client)* [📋](agent:copy?block=create-client) [✨](agent:ask?block=create-client)

```ruby
require 'plinth'
# A test key; never commit a live one. See https://docs.example.com/keys-safety.
client = Plinth::Client.new("vk_test_3Rb8Kw...q72NdX5e")
```

#### KEY FOR ONE REQUEST ... *[Ruby ↕](agent:choose-language?block=one-request-key)* [📋](agent:copy?block=one-request-key) [✨](agent:ask?block=one-request-key)

```ruby
booking = client.v3.bookings.retrieve(
  'bkg_4TfP7nYcM2qJ6sV9hE1d',
  {},
  {
    api_key: 'vk_test_3Rb8Kw...q72NdX5e'
  }
)
booking.confirm() # Sends the same one-request API key.
```

#### YOUR TEST KEY

The examples on this page are filled in with your own test secret key, so each one runs as written. Only you can see it.
***
***
___

# Errors

[`✨ Ask about this section`](agent:ask-about-section?section=errors) | [`📋 Copy for LLM`](agent:copy-for-llm?section=errors) | [`📄 View as Markdown`](/api/errors.md)

Plinth uses standard HTTP status codes to tell you whether a request succeeded. Broadly\: a code in the `2xx` range is a success. A code in the `4xx` range is an error caused by what the request sent (e.g., a required field was left out, the venue was already booked for those dates, etc.). A code in the `5xx` range is a fault on Plinth’s servers (these seldom happen).

Some `4xx` errors your integration can recover from on its own (e.g., a date that is [no longer available](/availability)) include an [error code](/error-codes) that says in a word what went wrong.

_Was this section helpful?_ - **[Yes](agent:helpful?section=errors&answer=yes)** **[No](agent:helpful?section=errors&answer=no)**

### Attributes

---

***`code`*** - _nullable string_
For errors your integration can recover from, a short string giving the [error code](/error-codes).

---

***`venue_code`*** - _nullable string_
For holds a venue declined, a short string with the [venue’s own reason](/venues#declines) when it gives one.

---

***`message`*** - _nullable string_
A human-readable message explaining the error in more detail. For availability errors, it is safe to show to your guests.

---

***`param`*** - _nullable string_
If the error is about one parameter, that parameter’s name. Use it to place the message next to the matching form field.

---

***`booking`*** - _nullable hash_
The [Booking object](/api/bookings/object) for errors returned by a request that touches a booking.

---

***`type`*** - _enum_
The category of the error. One of `api_error`, `availability_error`, `idempotency_error`, or `invalid_request_error`

| Possible enum values |
| --- |
| `api_error` |
| `availability_error` |
| `idempotency_error` |
| `invalid_request_error` |

### More ... [`Expand all`](agent:expand-all?section=errors)

- ***`advice_code`*** - _nullable string_
- ---
- ***`hold`*** - _nullable string_
- ---
- ***`doc_url`*** - _nullable string_
- ---
- ***`venue_advice_code`*** - _nullable string_
- ---
- ***`venue_decline_code`*** - _nullable string_
- ---
- ***`quote`*** - _nullable hash_
- ---
- ***`quote_tier`*** - _nullable string_
- ---
- ***`request_log_url`*** - _nullable string_
- ---
- ***`deposit`*** - _nullable hash_
- ---
- ***`waitlist_entry`*** - _nullable hash_
***

#### HTTP STATUS CODE SUMMARY

| | | |
| --- | --- | --- |
| **200** | OK | Everything worked as expected. |
| **400** | Bad Request | The request was not accepted, usually because a required parameter was missing. |
| **401** | Unauthorized | The request carried no valid API key. |
| **402** | Request Failed | The parameters were fine, but the request did not succeed. |
| **403** | Forbidden | This API key has no permission for the request. |
| **404** | Not Found | The object you asked for does not exist. |
| **409** | Conflict | The request conflicts with another one (it may have reused an idempotency key). |
| **424** | External Dependency Failed | A venue system or another outside service failed, so the request could not complete. |
| **429** | Too Many Requests | Requests came in too fast. Slow down with exponential backoff and try again. |
| **500, 502, 503, 504** | Server Errors | Something went wrong on Plinth’s end. (These are rare.) |

#### ERROR TYPES

| | |
| --- | --- |
| `api_error` | API errors cover any other kind of problem (e.g., a short interruption on Plinth’s servers), and seldom occur. |
| `availability_error` | Availability errors are the ones you should expect most. They occur when a guest asks for dates or a room that is already taken. |
| `idempotency_error` | Idempotency errors occur when an `Idempotency-Key` is sent again with a different endpoint or different parameters from the first request. |
| `invalid_request_error` | Invalid request errors occur when a request includes parameters that are not valid. |
***
***
___

# Handling errors

[`✨ Ask about this section`](agent:ask-about-section?section=handling-errors) | [`📋 Copy for LLM`](agent:copy-for-llm?section=handling-errors) | [`📄 View as Markdown`](/api/errors/handling.md)

The client libraries raise an exception for many kinds of failure, including a declined hold, bad parameters, failed authentication and network trouble. Make sure your code deals with each API exception gracefully.

Related guide: [Handling errors](/handling-errors)

#### ... *[Ruby ↕](agent:choose-language?block=handling-errors)* [📋](agent:copy?block=handling-errors) [✨](agent:ask?block=handling-errors)

```ruby
begin
  # Make requests with the Plinth library...
rescue Plinth::AvailabilityError => e
  # The dates or room are no longer free
  puts "Status: #{e.http_status}"
  puts "Type: #{e.error.type}"
  puts "Code: #{e.error.code}" if e.error.code
  puts "Venue code: #{e.error.venue_code}" if e.error.venue_code
  puts "Param: #{e.error.param}" if e.error.param
  puts "Message: #{e.error.message}"
  puts "Request ID: #{e.request_id}"
rescue Plinth::RateLimitError => e
  # The API received too many requests too quickly
  puts "Request ID: #{e.request_id}"
rescue Plinth::InvalidRequestError => e
  # The request had parameters that were not valid
  puts "Request ID: #{e.request_id}"
rescue Plinth::AuthenticationError => e
  # The Plinth API could not authenticate the request
  # (the API key may have been rolled)
  puts "Request ID: #{e.request_id}"
rescue Plinth::APIConnectionError => e
  # The connection to Plinth's servers failed
  puts "Request ID: #{e.request_id}"
rescue Plinth::PlinthError => e
  # Show the user a generic error, and consider
  # alerting yourself
  puts "Request ID: #{e.request_id}"
rescue => e
  # A failure that has nothing to do with Plinth
end
```
***
***
___

# Expanding Responses

[`✨ Ask about this section`](agent:ask-about-section?section=expanding) | [`📋 Copy for LLM`](agent:copy-for-llm?section=expanding) | [`📄 View as Markdown`](/api/expanding_objects.md)

Many objects can include more detail in an expanded response, which you ask for with the `expand` request parameter. Any API request accepts it, and it affects that request’s response alone. Expansion works in two ways.

Objects often carry the ID of a related object as one of their properties. A `Booking`, for instance, may carry a Guest ID. The expand parameter replaces such IDs with the full objects in the same response. Fields marked `expandable` on these pages are the IDs you can expand this way.

Some fields are omitted from responses unless you ask, such as the `door_code` and `wifi_password` fields on the Room object. Request them as an expanded response with the `expand` parameter.

Expansion can go several levels down: separate the nested field names with a dot (`.`). Requesting `quote.venue` on a booking, for example, expands the `quote` property into a complete Quote object, then expands that quote’s `venue` property into a complete Venue object.

The `expand` parameter is accepted by every endpoint that returns expandable fields, list, create and update endpoints among them.

On list requests, expansions start from the `data` property. You might, for example, expand `data.guests` on a request that lists bookings along with their guests. Deep expansions across large list requests can make responses slower.

An expansion may reach four levels at most (when listing bookings, for instance, the deepest one allowed is `data.quote.venue.default_room`).

To expand several objects in one request, list each of them in the `expand` array.

- Related guide: [Expanding responses](/expand)
- Related video: [Expand](https://video.example.com/watch?v=expand-basics)

_Was this section helpful?_ - **[Yes](agent:helpful?section=expanding&answer=yes)** **[No](agent:helpful?section=expanding&answer=no)**
