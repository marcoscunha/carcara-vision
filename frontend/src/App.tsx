import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { ThemeProvider, createTheme, alpha } from '@mui/material'
import CssBaseline from '@mui/material/CssBaseline'

import { AuthProvider, ProtectedRoute } from './auth'
import Layout from './components/Layout'
import Cameras from './pages/Cameras'
import Alarms from './pages/Alarms'
import Streams from './pages/Streams'
import Settings from './pages/Settings'
import Login from './pages/Login'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      gcTime: 1000 * 60 * 30, // 30 minutes (formerly cacheTime)
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

// Carcara Vision Color Palette
const colors = {
  background: {
    light: '#F9FAFB',
    cream: '#E3D3B0',
  },
  primary: {
    main: '#F5A45A', // Vibrant orange
    dark: '#D26A27', // Dark rust orange
    light: '#FFB97A',
    contrastText: '#181A1F',
  },
  neutral: {
    dark: '#181A1F', // Near black
    gray: '#484F57', // Dark gray
    lightGray: '#6B7280',
  },
}

const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: colors.primary.main,
      dark: colors.primary.dark,
      light: colors.primary.light,
      contrastText: colors.primary.contrastText,
    },
    secondary: {
      main: colors.background.cream,
      dark: '#C9B896',
      light: '#F0E8D8',
      contrastText: colors.neutral.dark,
    },
    background: {
      default: '#0D0E10',
      paper: colors.neutral.dark,
    },
    text: {
      primary: colors.background.light,
      secondary: '#9CA3AF',
    },
    error: {
      main: '#EF4444',
      light: '#F87171',
    },
    warning: {
      main: colors.primary.main,
    },
    success: {
      main: '#10B981',
      light: '#34D399',
    },
    divider: alpha(colors.neutral.gray, 0.3),
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h1: {
      fontWeight: 700,
      letterSpacing: '-0.02em',
    },
    h2: {
      fontWeight: 700,
      letterSpacing: '-0.02em',
    },
    h3: {
      fontWeight: 600,
      letterSpacing: '-0.01em',
    },
    h4: {
      fontWeight: 600,
      letterSpacing: '-0.01em',
    },
    h5: {
      fontWeight: 600,
    },
    h6: {
      fontWeight: 600,
    },
    button: {
      fontWeight: 600,
      textTransform: 'none',
    },
  },
  shape: {
    borderRadius: 12,
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          scrollbarColor: `${colors.neutral.gray} ${colors.neutral.dark}`,
          '&::-webkit-scrollbar, & *::-webkit-scrollbar': {
            width: 8,
            height: 8,
          },
          '&::-webkit-scrollbar-thumb, & *::-webkit-scrollbar-thumb': {
            borderRadius: 8,
            backgroundColor: colors.neutral.gray,
          },
          '&::-webkit-scrollbar-track, & *::-webkit-scrollbar-track': {
            backgroundColor: colors.neutral.dark,
          },
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: colors.neutral.dark,
          backgroundImage: 'none',
          borderBottom: `1px solid ${alpha(colors.neutral.gray, 0.2)}`,
          boxShadow: 'none',
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: colors.neutral.dark,
          backgroundImage: 'none',
          borderRight: `1px solid ${alpha(colors.neutral.gray, 0.2)}`,
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundColor: alpha(colors.neutral.dark, 0.8),
          backgroundImage: 'none',
          border: `1px solid ${alpha(colors.neutral.gray, 0.15)}`,
          boxShadow: `0 4px 20px ${alpha('#000', 0.25)}`,
          transition: 'transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out, border-color 0.2s ease-in-out',
          '&:hover': {
            transform: 'translateY(-2px)',
            boxShadow: `0 8px 30px ${alpha('#000', 0.35)}`,
            borderColor: alpha(colors.primary.main, 0.3),
          },
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          padding: '10px 20px',
          boxShadow: 'none',
          '&:hover': {
            boxShadow: 'none',
          },
        },
        contained: {
          background: `linear-gradient(135deg, ${colors.primary.main} 0%, ${colors.primary.dark} 100%)`,
          color: colors.primary.contrastText,
          '&:hover': {
            background: `linear-gradient(135deg, ${colors.primary.light} 0%, ${colors.primary.main} 100%)`,
          },
        },
        containedError: {
          background: `linear-gradient(135deg, #EF4444 0%, #DC2626 100%)`,
          color: '#fff',
          '&:hover': {
            background: `linear-gradient(135deg, #F87171 0%, #EF4444 100%)`,
          },
        },
        outlined: {
          borderColor: alpha(colors.primary.main, 0.5),
          '&:hover': {
            borderColor: colors.primary.main,
            backgroundColor: alpha(colors.primary.main, 0.08),
          },
        },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: {
          transition: 'all 0.2s ease-in-out',
          '&:hover': {
            backgroundColor: alpha(colors.neutral.gray, 0.2),
          },
        },
        colorPrimary: {
          color: colors.primary.main,
          '&:hover': {
            color: colors.primary.light,
            backgroundColor: alpha(colors.primary.main, 0.15),
          },
        },
        colorError: {
          color: '#EF4444',
          '&:hover': {
            color: '#F87171',
            backgroundColor: alpha('#EF4444', 0.15),
          },
        },
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          margin: '2px 8px',
          '&:hover': {
            backgroundColor: alpha(colors.primary.main, 0.08),
          },
          '&.Mui-selected': {
            backgroundColor: alpha(colors.primary.main, 0.15),
            borderLeft: `3px solid ${colors.primary.main}`,
            '&:hover': {
              backgroundColor: alpha(colors.primary.main, 0.2),
            },
          },
        },
      },
    },
    MuiListItemIcon: {
      styleOverrides: {
        root: {
          color: colors.neutral.lightGray,
          minWidth: 40,
          '.Mui-selected &': {
            color: colors.primary.main,
          },
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            '& fieldset': {
              borderColor: alpha(colors.neutral.gray, 0.3),
            },
            '&:hover fieldset': {
              borderColor: alpha(colors.primary.main, 0.5),
            },
            '&.Mui-focused fieldset': {
              borderColor: colors.primary.main,
            },
          },
        },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          backgroundColor: colors.neutral.dark,
          backgroundImage: 'none',
          border: `1px solid ${alpha(colors.neutral.gray, 0.2)}`,
          boxShadow: `0 25px 50px -12px ${alpha('#000', 0.5)}`,
        },
      },
    },
    MuiDialogTitle: {
      styleOverrides: {
        root: {
          borderBottom: `1px solid ${alpha(colors.neutral.gray, 0.2)}`,
          paddingBottom: 16,
        },
      },
    },
    MuiDialogActions: {
      styleOverrides: {
        root: {
          borderTop: `1px solid ${alpha(colors.neutral.gray, 0.2)}`,
          paddingTop: 16,
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 500,
        },
        colorSuccess: {
          backgroundColor: alpha('#10B981', 0.15),
          color: '#34D399',
        },
        colorError: {
          backgroundColor: alpha('#EF4444', 0.15),
          color: '#F87171',
        },
      },
    },
    MuiDivider: {
      styleOverrides: {
        root: {
          borderColor: alpha(colors.neutral.gray, 0.2),
        },
      },
    },
    MuiTooltip: {
      styleOverrides: {
        tooltip: {
          backgroundColor: colors.neutral.gray,
          fontSize: '0.75rem',
        },
      },
    },
  },
})

const App: React.FC = () => {
  return (
    <AuthProvider>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider theme={theme}>
          <CssBaseline />
          <Router>
            <Routes>
              {/* Public route: Login page */}
              <Route path="/login" element={<Login />} />

              {/* Protected routes: require authentication */}
              <Route
                path="/*"
                element={
                  <ProtectedRoute>
                    <Layout>
                      <Routes>
                        <Route path="/" element={<Navigate to="/cameras" replace />} />
                        <Route path="/cameras" element={<Cameras />} />
                        <Route path="/streams" element={<Streams />} />
                        <Route path="/alarms" element={<Alarms />} />
                        <Route path="/settings" element={<Settings />} />
                      </Routes>
                    </Layout>
                  </ProtectedRoute>
                }
              />
            </Routes>
          </Router>
        </ThemeProvider>
        <ReactQueryDevtools initialIsOpen={false} />
      </QueryClientProvider>
    </AuthProvider>
  )
}

export default App
