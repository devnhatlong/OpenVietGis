# OpenVietGIS Modules

Vertical domain modules live below this boundary.

Allowed dependency direction:

```text
vertical module -> public platform contract
platform/Core   -X-> vertical module
```

Spec 001 intentionally ships no runtime domain module. The platform must build, start, and validate
with this directory empty or absent.
