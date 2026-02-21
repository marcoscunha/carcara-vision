/**
 * Keycloak configuration for the frontend SPA.
 *
 * Uses PKCE (Proof Key for Code Exchange) for secure authentication
 * without requiring a client secret.
 */
import Keycloak from 'keycloak-js'

const parseAuthEnabled = (value: string | undefined): boolean => {
  if (!value) return true
  return ['1', 'true', 'yes', 'on'].includes(value.toLowerCase())
}

export const AUTH_ENABLED = parseAuthEnabled(import.meta.env.VITE_AUTH_ENABLED)

const keycloakUrl = import.meta.env.VITE_KEYCLOAK_URL || `${window.location.protocol}//${window.location.hostname}:8280`

const keycloakConfig = {
  url: keycloakUrl,
  realm: import.meta.env.VITE_KEYCLOAK_REALM || 'carcara',
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID || 'carcara-frontend',
}

const keycloak = new Keycloak(keycloakConfig)

export default keycloak
export { keycloakConfig }
