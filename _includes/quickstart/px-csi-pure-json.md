PX-CSI discovers every array from a single JSON file held in one secret. FlashArray and FlashBlade entries go in the same file. `NFSEndPoint` is required on a FlashBlade entry, and required on a FlashArray entry when you use File Services.

```json
{
  "FlashArrays": [
    {
      "MgmtEndPoint": "<fa-management-endpoint>",
      "APIToken": "<fa-api-token>",
      "NFSEndPoint": "<fa-file-vif>"
    }
  ],
  "FlashBlades": [
    {
      "MgmtEndPoint": "<fb-management-endpoint>",
      "APIToken": "<fb-api-token>",
      "NFSEndPoint": "<fb-data-vip>"
    }
  ]
}
```

Include only the array types you are configuring. Optional per-entry fields include `Realm` for secure multi-tenancy and `Labels` with `topology.portworx.io/*` keys for CSI topology. IPv6 addresses are written in square brackets, for example `"MgmtEndPoint": "[2001:db8::10]"`.

> **Important:** The secret must be named exactly `px-pure-secret` and must live in the namespace where PX-CSI is installed. PX-CSI looks for that name at startup.

Credentials are re-read periodically, so arrays added to the file later are discovered without reinstalling. If a newly added array is not discovered, restart the Portworx pods so the CSI components reload the secret immediately.
