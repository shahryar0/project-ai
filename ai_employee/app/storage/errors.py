class StorageUnavailableError(RuntimeError):
    pass


class CampaignConflictError(RuntimeError):
    pass


class RecordNotFoundError(LookupError):
    pass
