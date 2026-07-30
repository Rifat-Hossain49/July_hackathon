# Shongket laptop access-point launcher

The laptop launcher gives everyone on one local Wi-Fi the same numeric link,
for example:

```text
http://192.168.0.29:8787
```

It does not provide Internet access or connect unrelated Wi-Fi networks.
Everyone must join the same access point as the laptop. The laptop must remain
powered, connected and running.

For that numeric link to stay unchanged, reserve the laptop's Wi-Fi address in
the access point's DHCP settings. The optional mDNS package also advertises
`http://shongket.local:8787`, but `.local` browser resolution varies by device
and access point, so it is not the universal fallback.

## Install once

From the repository root:

```text
python -m pip install -r deploy/local_access_point/requirements.txt
```

## Start

```text
python -m bdix_hub --access-point
```

The launcher prints the exact Wi-Fi URL and an optional friendly name. Allow
Python on Windows **Private networks** if the firewall asks. Do not enable it
on an untrusted public Wi-Fi.

If automatic address selection chooses the wrong adapter:

```text
python -m bdix_hub --access-point --advertise-address 192.168.0.29
```

## Client steps

1. Join the laptop's Wi-Fi or access point.
2. Open `http://shongket.local:8787`.
3. Open the numeric Wi-Fi link printed by the laptop. You may try the optional
   `shongket.local` link if that device supports it.
4. Join the same incident channel.

Some access points block multicast or isolate clients. Shongket cannot bypass
those router policies. Local HTTP is not encrypted, so this mode is for a
trusted nearby network and public crisis capsules only.
