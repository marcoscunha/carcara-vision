import React, { useState, useEffect } from 'react'
import { Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, TextField, Typography } from '@mui/material'

export interface ConfirmDeleteDialogProps {
  open: boolean
  onClose: () => void
  onConfirm: () => void
  title: string
  itemName: string
  warningMessage?: string
  isLoading?: boolean
}

export const ConfirmDeleteDialog: React.FC<ConfirmDeleteDialogProps> = ({
  open,
  onClose,
  onConfirm,
  title,
  itemName,
  warningMessage,
  isLoading = false,
}) => {
  const [confirmText, setConfirmText] = useState('')

  // Reset confirmation text when dialog opens/closes
  useEffect(() => {
    if (!open) {
      setConfirmText('')
    }
  }, [open])

  const isConfirmValid = confirmText.toLowerCase() === 'delete'

  const handleConfirm = () => {
    if (isConfirmValid) {
      onConfirm()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && isConfirmValid && !isLoading) {
      handleConfirm()
    }
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle className="confirm-delete__title">{title}</DialogTitle>
      <DialogContent>
        <Box className="confirm-delete__content">
          <Typography variant="body1" className="confirm-delete__message">
            Are you sure you want to delete <strong>"{itemName}"</strong>?
          </Typography>

          {warningMessage && (
            <Box className="confirm-delete__warning">
              <Typography variant="body2" color="warning.dark" className="confirm-delete__warning-text">
                ⚠️ {warningMessage}
              </Typography>
            </Box>
          )}

          <Typography variant="body2" color="text.secondary" className="confirm-delete__prompt">
            To confirm, please type <strong>delete</strong> below:
          </Typography>
          <TextField
            autoFocus
            fullWidth
            size="small"
            placeholder="Type 'delete' to confirm"
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            className={`confirm-delete__input ${isConfirmValid ? 'confirm-delete__input--valid' : ''}`}
          />
        </Box>
      </DialogContent>
      <DialogActions className="confirm-delete__actions">
        <Button onClick={onClose} variant="outlined" disabled={isLoading}>
          Cancel
        </Button>
        <Button onClick={handleConfirm} variant="contained" color="error" disabled={!isConfirmValid || isLoading}>
          {isLoading ? 'Deleting...' : 'Delete'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

export default ConfirmDeleteDialog
