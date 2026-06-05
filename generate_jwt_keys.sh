#!/bin/bash

# Generate JWT RSA Keys for FixitLab Production
# Usage: ./generate_jwt_keys.sh

echo "╔═════════════════════════════════════════════════════════╗"
echo "║   Generating JWT RS256 RSA Keys for FixitLab            ║"
echo "╚═════════════════════════════════════════════════════════╝"
echo ""

# Generate RSA Private Key (2048-bit)
echo "📝 Generating RSA 2048-bit private key..."
openssl genrsa -out jwt_private.key 2048

# Extract RSA Public Key
echo "📝 Extracting RSA public key..."
openssl rsa -in jwt_private.key -pubout -out jwt_public.key

# Convert keys to single-line format for .env file
echo ""
echo "╔═════════════════════════════════════════════════════════╗"
echo "║   Add these to your .env file:                          ║"
echo "╚═════════════════════════════════════════════════════════╝"
echo ""

echo "JWT_ALGORITHM=RS256"
echo "JWT_ACCESS_TOKEN_LIFETIME=3600"
echo "JWT_REFRESH_TOKEN_LIFETIME=604800"
echo ""

echo "# Private Key (keep this SECRET):"
echo "JWT_SIGNING_KEY=$(sed ':a;N;$!ba;s/\n/\\n/g' jwt_private.key)"
echo ""

echo "# Public Key:"
echo "JWT_VERIFYING_KEY=$(sed ':a;N;$!ba;s/\n/\\n/g' jwt_public.key)"
echo ""

echo "╔═════════════════════════════════════════════════════════╗"
echo "║   Files created:                                        ║"
echo "║   - jwt_private.key (DO NOT COMMIT)                     ║"
echo "║   - jwt_public.key (safe to commit)                     ║"
echo "╚═════════════════════════════════════════════════════════╝"
echo ""

# Display raw key files
echo "─── RAW PRIVATE KEY ───"
cat jwt_private.key
echo ""
echo "─── RAW PUBLIC KEY ───"
cat jwt_public.key
echo ""

echo "✅ Keys generated successfully!"
echo "⚠️  IMPORTANT: Keep jwt_private.key secure and do NOT commit it to git!"
echo ""
echo "Next steps:"
echo "1. Open your .env file"
echo "2. Find JWT_SIGNING_KEY and JWT_VERIFYING_KEY"
echo "3. Copy-paste the values above"
echo "4. In .env, replace actual newlines with \\n (already done above)"
echo "5. Delete jwt_private.key and jwt_public.key after updating .env"
