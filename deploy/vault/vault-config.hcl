storage "file" {
  path = "/vault/file"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = 1
}

ui = true

# Disable mlock to avoid requiring IPC_LOCK capability issues
disable_mlock = true

# API address for Vault to advertise
api_addr = "http://0.0.0.0:8200"
