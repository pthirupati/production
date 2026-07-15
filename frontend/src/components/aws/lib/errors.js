// Byte-accurate AWS error strings.
//
// Real AWS CLI / SDK surface errors in the shape:
//   An error occurred (Code) when calling the Op operation: message
// These factories produce exactly that string so the console + CLI can show
// something indistinguishable from the real thing. Each returns a plain
// { code, op, message, str } object; `str` is the fully formatted line.

/** Format the canonical AWS error line. */
export function awsErrorString(code, op, message) {
  return `An error occurred (${code}) when calling the ${op} operation: ${message}`
}

function make(code, op, message) {
  return { code, op, message, str: awsErrorString(code, op, message) }
}

// ---- EC2 / VPC dependency + parameter errors ----
export const dependencyViolation = (op, message) =>
  make('DependencyViolation', op, message)

export const invalidGroupInUse = (op, message) =>
  make('InvalidGroup.InUse', op, message || 'resource sg is currently in use.')

export const invalidParameterValue = (op, message) =>
  make('InvalidParameterValue', op, message)

export const unauthorizedOperation = (op) =>
  make('UnauthorizedOperation', op, 'You are not authorized to perform this operation.')

export const operationNotPermitted = (op, message) =>
  make('OperationNotPermitted', op, message)

// ---- S3 ----
export const bucketNotEmpty = (op, message) =>
  make('BucketNotEmpty', op || 'DeleteBucket', message || 'The bucket you tried to delete is not empty')

// ---- IAM / policy ----
export const malformedPolicyDocument = (op, message) =>
  make('MalformedPolicyDocument', op || 'CreatePolicy', message)

export const accessDenied = (op, message) =>
  make('AccessDenied', op, message || 'User is not authorized to perform this action.')

// ---- Generic service (Lambda/DynamoDB/etc.) ----
export const resourceNotFound = (op, message) =>
  make('ResourceNotFoundException', op, message)

// Convenience: a store write returns this shape on a guarded failure.
export const fail = (errObj) => ({ ok: false, error: errObj.str, code: errObj.code })
export const ok = (extra) => ({ ok: true, ...(extra || {}) })
