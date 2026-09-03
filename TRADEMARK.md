# Trademark Policy

The HEBOM mark is held by **Space A** (스페이스 에이).

The **code** in this repository is licensed under Apache-2.0. You may fork,
modify, redistribute and sell it. That is intentional.

The **name** is not part of that licence.

## You may
- say your product "works with HEBOM Buffer" or "is compatible with the
  HEBOM result schema"
- publish results in the `hebom.org/schema/buffer-result/1` format
- fork this repository under a different name

## You may not
- publish a fork under the name "HEBOM", "HEBOM Buffer" or a confusingly
  similar name
- use the name to describe an operated service that is not ours
- imply endorsement or certification by HEBOM

This is the same split Linux and PostgreSQL use: open code, protected name.
It exists so that "HEBOM said this pipeline passed" means one thing.

## "HEBOM verified" means one specific thing

Results carry an `origin` field:

| origin | meaning |
|---|---|
| `local` | you ran the open-source package yourself |
| `third_party` | an independent operator ran it |
| `hebom_verified` | ⛔ **only** HEBOM's operated verification service |

Downloading the code and getting a PASS on your laptop is `local`. It is not a
HEBOM verification and must not be described as one. The package refuses to
emit `hebom_verified` — that value exists only in the operated service.

This separation is what makes the phrase worth anything.

Questions: hello@justholdings.io
