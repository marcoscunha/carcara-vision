/**
 * Authentication Provider for Carcara NVC.
 *
 * Provides React context for authentication state and operations.
 * Uses Keycloak for OAuth2/OIDC authentication with PKCE flow.
 */
import React, { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react'
import keycloak from './keycloak'

/**
 * User information extracted from the Keycloak token.
 */
export interface User {
  id: string
  username: string
  email?: string
  firstName?: string
  lastName?: string
  roles: string[]
}

/**
 * Authentication context type.
 */
interface AuthContextType {
  /** Whether the user is authenticated */
  isAuthenticated: boolean
  /** Whether authentication is still initializing */
  isLoading: boolean
  /** Current user information, null if not authenticated */
  user: User | null
  /** Current access token, null if not authenticated */
  token: string | null
  /** Initiate login flow */
  login: () => void
  /** Logout and clear session */
  logout: () => void
  /** Check if user has a specific role */
  hasRole: (role: string) => boolean
  /** Check if user is admin */
  isAdmin: boolean
  /** Manually refresh the token */
  refreshToken: () => Promise<boolean>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

interface AuthProviderProps {
  children: ReactNode
}

/**
 * Authentication Provider Component.
 *
 * Wraps the application and provides authentication state via React context.
 * Initializes Keycloak on mount and handles token refresh automatically.
 */
export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)

  /**
   * Extract user information from Keycloak token.
   */
  const extractUser = useCallback((): User | null => {
    if (!keycloak.tokenParsed) return null

    const tokenParsed = keycloak.tokenParsed as {
      sub?: string
      preferred_username?: string
      email?: string
      given_name?: string
      family_name?: string
      roles?: string[]
      realm_access?: { roles?: string[] }
    }

    // Get roles from multiple possible locations
    const roles: string[] = []

    // From custom 'roles' claim
    if (Array.isArray(tokenParsed.roles)) {
      roles.push(...tokenParsed.roles)
    }

    // From realm_access.roles
    if (tokenParsed.realm_access?.roles) {
      roles.push(...tokenParsed.realm_access.roles)
    }

    // Deduplicate
    const uniqueRoles = [...new Set(roles)]

    return {
      id: keycloak.subject || '',
      username: tokenParsed.preferred_username || '',
      email: tokenParsed.email,
      firstName: tokenParsed.given_name,
      lastName: tokenParsed.family_name,
      roles: uniqueRoles,
    }
  }, [])

  /**
   * Update authentication state from Keycloak.
   */
  const updateAuthState = useCallback(() => {
    setIsAuthenticated(keycloak.authenticated || false)
    setToken(keycloak.token || null)
    setUser(keycloak.authenticated ? extractUser() : null)
  }, [extractUser])

  /**
   * Refresh the access token.
   */
  const refreshToken = useCallback(async (): Promise<boolean> => {
    try {
      const refreshed = await keycloak.updateToken(30)
      if (refreshed) {
        updateAuthState()
      }
      return refreshed
    } catch (error) {
      console.error('Token refresh failed:', error)
      setIsAuthenticated(false)
      setUser(null)
      setToken(null)
      return false
    }
  }, [updateAuthState])

  /**
   * Initialize Keycloak on component mount.
   */
  useEffect(() => {
    const initKeycloak = async () => {
      try {
        // Initialize Keycloak with check-sso to detect existing sessions
        const authenticated = await keycloak.init({
          onLoad: 'check-sso',
          silentCheckSsoRedirectUri: window.location.origin + '/silent-check-sso.html',
          pkceMethod: 'S256',
          checkLoginIframe: false, // Disable iframe check for better compatibility
        })

        console.log('Keycloak initialized, authenticated:', authenticated)

        if (authenticated) {
          updateAuthState()
        }

        // Handle token expiration
        keycloak.onTokenExpired = () => {
          console.log('Token expired, refreshing...')
          refreshToken()
        }

        // Handle auth success (after redirect back from Keycloak)
        keycloak.onAuthSuccess = () => {
          console.log('Auth success')
          updateAuthState()
        }

        // Handle auth error
        keycloak.onAuthError = (errorData: { error: string; error_description: string }) => {
          console.error('Auth error:', errorData)
          setIsAuthenticated(false)
          setUser(null)
          setToken(null)
        }

        // Handle logout
        keycloak.onAuthLogout = () => {
          console.log('User logged out')
          setIsAuthenticated(false)
          setUser(null)
          setToken(null)
        }
      } catch (error) {
        console.error('Keycloak initialization failed:', error)
        setIsAuthenticated(false)
      } finally {
        setIsLoading(false)
      }
    }

    initKeycloak()
  }, [updateAuthState, refreshToken])

  /**
   * Initiate login flow.
   */
  const login = useCallback(() => {
    keycloak.login()
  }, [])

  /**
   * Logout and redirect to home.
   */
  const logout = useCallback(() => {
    keycloak.logout({
      redirectUri: window.location.origin,
    })
  }, [])

  /**
   * Check if user has a specific role.
   */
  const hasRole = useCallback(
    (role: string): boolean => {
      return user?.roles.includes(role) || false
    },
    [user],
  )

  /**
   * Check if user is admin.
   */
  const isAdmin = user?.roles.includes('admin') || false

  const value: AuthContextType = {
    isAuthenticated,
    isLoading,
    user,
    token,
    login,
    logout,
    hasRole,
    isAdmin,
    refreshToken,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

/**
 * Hook to access authentication context.
 *
 * @throws Error if used outside of AuthProvider
 */
export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

export default AuthProvider
