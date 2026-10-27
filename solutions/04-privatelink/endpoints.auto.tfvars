# End state of challenge 4: three namespaces forwarded from NIOS (adding queue
# was one line) and four private endpoints across two storage accounts.
nios_forward_namespaces = [
  "privatelink.blob.core.windows.net",
  "privatelink.file.core.windows.net",
  "privatelink.queue.core.windows.net",
]

private_endpoints = {
  "sa-a-blob"  = { account = "a", subresource = "blob" }
  "sa-b-blob"  = { account = "b", subresource = "blob" }
  "sa-a-file"  = { account = "a", subresource = "file" }
  "sa-a-queue" = { account = "a", subresource = "queue" }
}
