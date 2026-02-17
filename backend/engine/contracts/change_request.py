def mark_reviewed(change_request):
    change_request.status = "reviewed"
    change_request.save(update_fields=["status"])

