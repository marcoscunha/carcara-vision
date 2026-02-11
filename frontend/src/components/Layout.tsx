import React from 'react'
import {
  AppBar,
  Box,
  CssBaseline,
  Drawer,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
} from '@mui/material'
import {
  Menu as MenuIcon,
  Videocam as CameraIcon,
  PlayCircle as StreamIcon,
  Notifications as AlarmIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material'
import { useNavigate, useLocation } from 'react-router-dom'

interface LayoutProps {
  children: React.ReactNode
}

// CARCARA Logo Component
const CarcaraLogo: React.FC<{ size?: 'small' | 'large' }> = ({ size = 'large' }) => {
  const isSmall = size === 'small'

  return (
    <Box className={`carcara-logo ${isSmall ? 'carcara-logo--small' : ''}`}>
      {/* Logo Icon - Bird/Hawk silhouette representing Carcara */}
      <Box className="carcara-logo__mark">
        {/* Stylized "C" for Carcara */}
        <Typography className="carcara-logo__letter">C</Typography>
      </Box>

      {/* Brand Text */}
      <Box className="carcara-logo__text">
        <Typography variant={isSmall ? 'subtitle1' : 'h6'} className="carcara-logo__title">
          CARCARA
        </Typography>
        <Typography className="carcara-logo__subtitle">NVC</Typography>
      </Box>
    </Box>
  )
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const [mobileOpen, setMobileOpen] = React.useState(false)
  const navigate = useNavigate()
  const location = useLocation()

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen)
  }

  const menuItems = [
    { text: 'Cameras', icon: <CameraIcon />, path: '/cameras' },
    { text: 'Streams', icon: <StreamIcon />, path: '/streams' },
    { text: 'Alarms', icon: <AlarmIcon />, path: '/alarms' },
    { text: 'Settings', icon: <SettingsIcon />, path: '/settings' },
  ]

  const isActive = (path: string) => location.pathname === path || (path === '/cameras' && location.pathname === '/')

  const drawer = (
    <Box className="layout__drawer-body">
      {/* Logo Section */}
      <Box className="layout__logo">
        <CarcaraLogo />
      </Box>

      {/* Navigation */}
      <Box className="layout__nav">
        <Typography variant="overline" className="layout__nav-label">
          Main Menu
        </Typography>
        <List className="layout__nav-list">
          {menuItems.map((item) => (
            <ListItem key={item.text} disablePadding className="layout__nav-item">
              <ListItemButton
                onClick={() => navigate(item.path)}
                selected={isActive(item.path)}
                className="layout__nav-button"
              >
                <ListItemIcon className="layout__nav-icon">{item.icon}</ListItemIcon>
                <ListItemText
                  primary={item.text}
                  primaryTypographyProps={{
                    className: 'layout__nav-text',
                  }}
                />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
      </Box>

      {/* Footer */}
      <Box className="layout__footer">
        <Typography variant="caption" className="layout__footer-text">
          Network Video Controller
        </Typography>
      </Box>
    </Box>
  )

  return (
    <Box className="layout">
      <CssBaseline />
      <AppBar position="fixed" className="layout__appbar">
        <Toolbar className="layout__toolbar">
          <Box className="layout__toolbar-left">
            <IconButton
              color="inherit"
              aria-label="open drawer"
              edge="start"
              onClick={handleDrawerToggle}
              className="layout__menu-button"
            >
              <MenuIcon />
            </IconButton>
            <Box className="layout__logo-small">
              <CarcaraLogo size="small" />
            </Box>
          </Box>

          {/* Page Title - Shows current page */}
          <Typography variant="h6" className="layout__page-title">
            {menuItems.find((item) => isActive(item.path))?.text || 'Dashboard'}
          </Typography>

          {/* Placeholder for future actions */}
          <Box className="layout__toolbar-spacer" />
        </Toolbar>
      </AppBar>
      <Box component="nav" className="layout__nav-container">
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{
            keepMounted: true,
          }}
          className="layout__drawer layout__drawer--temporary"
        >
          {drawer}
        </Drawer>
        <Drawer variant="permanent" className="layout__drawer layout__drawer--permanent" open>
          {drawer}
        </Drawer>
      </Box>
      <Box component="main" className="layout__main">
        <Toolbar />
        {children}
      </Box>
    </Box>
  )
}

export default Layout
