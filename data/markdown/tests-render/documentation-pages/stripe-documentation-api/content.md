<!-- Source: https://docs.stripe.com/api/ -->
# API Reference

[`✨ Ask about this section`](agent:ask-about-section?section=api-reference) | [`📋 Copy for LLM`](agent:copy-for-llm?section=api-reference) | [`📄 View as Markdown`](/api.md)

The Stripe API is organized around [REST](http://en.wikipedia.org/wiki/Representational_State_Transfer). Our API has predictable resource-oriented URLs, accepts [form-encoded](https://en.wikipedia.org/wiki/POST_%28HTTP%29#Use_for_submitting_web_forms) request bodies, returns [JSON-encoded](http://www.json.org/) responses, and uses standard HTTP response codes, authentication, and verbs.

You can use the Stripe API in [sandboxes](/sandboxes) without affecting your live data or interacting with banking networks. The API key that you use to [authenticate](/api/authentication) the request determines whether the request runs in live mode or in a sandbox. Sandboxes support all v2 APIs. Test mode sandboxes support some [v2 APIs](/testing-use-cases#compare).

The Stripe API doesn’t support bulk updates. You can work on only one object per request.

The Stripe API differs for every account as we release new [versions](/api/versioning) and tailor functionality. [Log in](https://dashboard.stripe.com/login?redirect=https%3A%2F%2Fdocs.stripe.com%2Fapi) to see docs with your test key and data.

_Was this section helpful?_ - **[Yes](agent:helpful?section=api-reference&answer=yes)** **[No](agent:helpful?section=api-reference&answer=no)**

## Just getting started?

Check out our [development quickstart](/get-started/development-environment) guide.

___

## Not a developer?

Use Stripe’s [no-code options](/payments/no-code) or apps from [our partners](https://stripe.partners/) to get started with Stripe and to do more with your Stripe account—no code required.
***

#### BASE URL ... [📋](agent:copy?block=base-url) [✨](agent:ask?block=base-url)

```text
https://api.stripe.com
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
$ gem install stripe
```
:::
... [🐙 STRIPE-RUBY](https://github.com/stripe/stripe-ruby)
:::0
___
***
***
___

# Authentication

[`✨ Ask about this section`](agent:ask-about-section?section=authentication) | [`📋 Copy for LLM`](agent:copy-for-llm?section=authentication) | [`📄 View as Markdown`](/api/authentication.md)

The Stripe API uses [API keys](/keys) to authenticate requests. You can view and manage your API keys in [the Stripe Dashboard](https://dashboard.stripe.com/login?redirect=/apikeys).

Test secret keys have the prefix `sk_test_` and live mode secret keys have the prefix `sk_live_`. Alternatively, you can use [restricted API keys](/keys#limit-access) for granular permissions.

Your API keys carry many privileges. Follow [best practices](/keys-best-practices) to keep your keys safe. Don’t embed secret (or restricted) API keys in source code or client-side applications. Instead, use your server platform’s secrets vault to provide keys to your server-side applications. If your platform doesn’t offer a secrets vault, set your keys in environment variables.

Use your API key by assigning it when creating [StripeClient](/api/stripe-client). The Ruby library will then automatically send this key in each request.

You can also set a per-request key with an option. This is often useful for Connect applications that use multiple API keys during the lifetime of a process. Methods on the returned object reuse the same API key.

Make all API requests over [HTTPS](http://en.wikipedia.org/wiki/HTTP_Secure). Calls made over plain HTTP fail. API requests without authentication also fail.

_Was this section helpful?_ - **[Yes](agent:helpful?section=authentication&answer=yes)** **[No](agent:helpful?section=authentication&answer=no)**

#### INITIALIZE STRIPECLIENT ... *[Ruby ↕](agent:choose-language?block=initialize-client)* [📋](agent:copy?block=initialize-client) [✨](agent:ask?block=initialize-client)

```ruby
require 'stripe'
# Test mode key; don't put live keys in code. See https://docs.stripe.com/keys-best-practices.
client = Stripe::StripeClient.new("sk_test_51TWKbD...p800mzrU3pg5")
```

#### PER-REQUEST API KEY ... *[Ruby ↕](agent:choose-language?block=per-request-key)* [📋](agent:copy?block=per-request-key) [✨](agent:ask?block=per-request-key)

```ruby
charge = client.v1.charges.retrieve(
  'ch_3P5pVZArEmbiH6tU1sg0W06t',
  {},
  {
    api_key: 'sk_test_51TWKbD...p800mzrU3pg5'
  }
)
charge.capture() # Uses the same request specific API Key.
```

#### YOUR API KEY {#panel-1}

Your test secret key is included in all the examples here, so you can test any example right away. Only you can see this value.
***
***
___

# Errors

[`✨ Ask about this section`](agent:ask-about-section?section=errors) | [`📋 Copy for LLM`](agent:copy-for-llm?section=errors) | [`📄 View as Markdown`](/api/errors.md)

Stripe uses conventional HTTP response codes to indicate the success or failure of an API request. In general\: Codes in the `2xx` range indicate success. Codes in the `4xx` range indicate an error that failed given the information provided (e.g., a required parameter was omitted, a charge failed, etc.). Codes in the `5xx` range indicate an error with Stripe’s servers (these are rare).

Some `4xx` errors that could be handled programmatically (e.g., a card is [declined](/declines)) include an [error code](/error-codes) that briefly explains the error reported.

_Was this section helpful?_ - **[Yes](agent:helpful?section=errors&answer=yes)** **[No](agent:helpful?section=errors&answer=no)**

### Attributes

---

***`code`*** - _nullable string_
For some errors that could be handled programmatically, a short string indicating the [error code](/error-codes) reported.

---

***`decline_code`*** - _nullable string_
For card errors resulting from a card issuer decline, a short string indicating the [card issuer’s reason for the decline](/declines#issuer-declines) if they provide one.

---

***`message`*** - _nullable string_
A human-readable message providing more details about the error. For card errors, these messages can be shown to your users.

---

***`param`*** - _nullable string_
If the error is parameter-specific, the parameter related to the error. For example, you can use this to display a message near the correct form field.

---

***`payment_intent`*** - _nullable hash_
The [PaymentIntent object](/api/payment_intents/object) for errors returned on a request involving a PaymentIntent.

---

***`type`*** - _enum_
The type of error returned. One of `api_error`, `card_error`, `idempotency_error`, or `invalid_request_error`

| Possible enum values |
| --- |
| `api_error` |
| `card_error` |
| `idempotency_error` |
| `invalid_request_error` |

### More ... [`Expand all`](agent:expand-all?section=errors)

- ***`advice_code`*** - _nullable string_
- ---
- ***`charge`*** - _nullable string_
- ---
- ***`doc_url`*** - _nullable string_
- ---
- ***`network_advice_code`*** - _nullable string_
- ---
- ***`network_decline_code`*** - _nullable string_
- ---
- ***`payment_method`*** - _nullable hash_
- ---
- ***`payment_method_type`*** - _nullable string_
- ---
- ***`request_log_url`*** - _nullable string_
- ---
- ***`setup_intent`*** - _nullable hash_
- ---
- ***`source`*** - _nullable hash_
***

#### HTTP STATUS CODE SUMMARY {#panel-2}

| | | |
| --- | --- | --- |
| **200** | OK | Everything worked as expected. |
| **400** | Bad Request | The request was unacceptable, often due to missing a required parameter. |
| **401** | Unauthorized | No valid API key provided. |
| **402** | Request Failed | The parameters were valid but the request failed. |
| **403** | Forbidden | The API key doesn’t have permissions to perform the request. |
| **404** | Not Found | The requested resource doesn’t exist. |
| **409** | Conflict | The request conflicts with another request (perhaps due to using the same idempotent key). |
| **424** | External Dependency Failed | The request couldn’t be completed due to a failure in a dependency external to Stripe. |
| **429** | Too Many Requests | Too many requests hit the API too quickly. We recommend an exponential backoff of your requests. |
| **500, 502, 503, 504** | Server Errors | Something went wrong on Stripe’s end. (These are rare.) |

#### ERROR TYPES {#panel-3}

| | |
| --- | --- |
| `api_error` | API errors cover any other type of problem (e.g., a temporary problem with Stripe’s servers), and are extremely uncommon. |
| `card_error` | Card errors are the most common type of error you should expect to handle. They result when the user enters a card that can’t be charged for some reason. |
| `idempotency_error` | Idempotency errors occur when an `Idempotency-Key` is re-used on a request that does not match the first request’s API endpoint and parameters. |
| `invalid_request_error` | Invalid request errors arise when your request has invalid parameters. |
***
***
___

# Handling errors

[`✨ Ask about this section`](agent:ask-about-section?section=handling-errors) | [`📋 Copy for LLM`](agent:copy-for-llm?section=handling-errors) | [`📄 View as Markdown`](/api/errors/handling.md)

Our Client libraries raise exceptions for many reasons, such as a failed charge, invalid parameters, authentication errors, and network unavailability. We recommend writing code that gracefully handles all possible API exceptions.

Related guide\: [Error Handling](/error-handling)

#### ... *[Ruby ↕](agent:choose-language?block=handling-errors)* [📋](agent:copy?block=handling-errors) [✨](agent:ask?block=handling-errors)

```ruby
begin
  # Use Stripe's library to make requests...
rescue Stripe::CardError => e
  # A declined card error
  puts "Status: #{e.http_status}"
  puts "Type: #{e.error.type}"
  puts "Code: #{e.error.code}" if e.error.code
  puts "Decline code: #{e.error.decline_code}" if e.error.decline_code
  puts "Param: #{e.error.param}" if e.error.param
  puts "Message: #{e.error.message}"
  puts "Request ID: #{e.request_id}"
rescue Stripe::RateLimitError => e
  # Too many requests made to the API too quickly
  puts "Request ID: #{e.request_id}"
rescue Stripe::InvalidRequestError => e
  # Invalid parameters were supplied to Stripe's API
  puts "Request ID: #{e.request_id}"
rescue Stripe::AuthenticationError => e
  # Authentication with Stripe's API failed
  # (maybe you changed API keys recently)
  puts "Request ID: #{e.request_id}"
rescue Stripe::APIConnectionError => e
  # Network communication with Stripe failed
  puts "Request ID: #{e.request_id}"
rescue Stripe::StripeError => e
  # Display a very generic error to the user, and maybe send
  # yourself an email
  puts "Request ID: #{e.request_id}"
rescue => e
  # Something else happened, completely unrelated to Stripe
end
```
***
***
___

# Expanding Responses

[`✨ Ask about this section`](agent:ask-about-section?section=expanding) | [`📋 Copy for LLM`](agent:copy-for-llm?section=expanding) | [`📄 View as Markdown`](/api/expanding_objects.md)

Many objects allow you to request additional information as an expanded response by using the `expand` request parameter. This parameter is available on all API requests, and applies to the response of that request only. You can expand responses in two ways.

In many cases, an object contains the ID of a related object in its response properties. For example, a `Charge` might have an associated Customer ID. You can expand these objects in line with the expand request parameter. The `expandable` label in this documentation indicates ID fields that you can expand into objects.

Some available fields aren’t included in the responses by default, such as the `number` and `cvc` fields for the Issuing Card object. You can request these fields as an expanded response by using the `expand` request parameter.

You can expand recursively by specifying nested fields after a dot (`.`). For example, requesting `payment_intent.customer` on a charge expands the `payment_intent` property into a full PaymentIntent object, then expands the `customer` property on that payment intent into a full Customer object.

You can use the `expand` parameter on any endpoint that returns expandable fields, including list, create, and update endpoints.

Expansions on list requests start with the `data` property. For example, you can expand `data.customers` on a request to list charges and associated customers. Performing deep expansions on numerous list requests might result in slower processing times.

Expansions have a maximum depth of four levels (for example, the deepest expansion allowed when listing charges is `data.payment_intent.customer.default_source`).

You can expand multiple objects at the same time by identifying multiple items in the `expand` array.

- Related guide\: [Expanding responses](/expand)
- Related video\: [Expand](https://www.youtube.com/watch?v=m8Vj_CEWyQc)

_Was this section helpful?_ - **[Yes](agent:helpful?section=expanding&answer=yes)** **[No](agent:helpful?section=expanding&answer=no)**
