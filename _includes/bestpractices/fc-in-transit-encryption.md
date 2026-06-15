### In-Transit Encryption

FlashArray supports encryption of FC frames in flight between host and array, providing wire-level confidentiality beyond fabric zoning. In-flight encryption operates on the HBA below the SCSI / FCP layer; LUN access, multipath, and ALUA behavior are unchanged, and the host-side `multipath.conf` and queue-depth settings apply identically whether encryption is enabled or not.
