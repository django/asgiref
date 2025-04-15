import gc

from asgiref.local import Local


def disable_gc_for_garbage_collection_test() -> None:
    # Disable automatic garbage collection. To have control over when
    # garbage collection is performed. This is necessary to ensure that another
    # that thread doesn't accidentally trigger it by simply executing code.
    gc.disable()

    # Delete the garbage list(`gc.garbage`) to ensure that other tests don't
    # interfere with this test.
    gc.collect()

    # Set the garbage collection debugging flag to store all unreachable
    # objects in `gc.garbage`. This is necessary to ensure that the
    # garbage list is empty after execute test code. Otherwise, the test
    # will always pass. The garbage list isn't automatically populated
    # because it costs extra CPU cycles
    gc.set_debug(gc.DEBUG_SAVEALL)


def clean_up_after_garbage_collection_test() -> None:
    # Clean up the garbage collection settings. Re-enable automatic garbage
    # collection. This step is mandatory to avoid running other tests without
    # automatic garbage collection.
    gc.set_debug(0)
    gc.enable()


def test_thread_critical_Local_remove_all_reference_cycles() -> None:
    try:
        # given
        # Disable automatic garbage collection and set debugging flag.
        disable_gc_for_garbage_collection_test()

        # when
        # Create thread critical Local object in sync context.
        try:
            getattr(Local(thread_critical=True), "missing")
        except AttributeError:
            pass
        # Enforce garbage collection to populate the garbage list for inspection.
        gc.collect()

        # then
        # Ensure that the garbage list is empty. The garbage list is only valid
        # until the next collection cycle so we can only make assertions about it
        # before re-enabling automatic collection.
        assert gc.garbage == []
    # Restore garbage collection settings to their original state. This should always be run to avoid interfering
    # with other tests to ensure that code should be executed in the `finally' block.
    finally:
        clean_up_after_garbage_collection_test()
