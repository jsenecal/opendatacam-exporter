from prometheus_client import Gauge, Counter

opendatacam_current_fps_gauge = Gauge(
    "opendatacam_current_fps",
    "Number of frames per second that are processed by yolo",
    labelnames=("site_name",),
)
opendatacam_recording_elapsed_seconds_gauge = Gauge(
    "opendatacam_recording_elapsed_seconds",
    "Time spent recording in seconds",
    labelnames=("site_name",),
)
opendatacam_recording_counter_data_gauge = Gauge(
    "opendatacam_recording_counter_data",
    "Counter data for a specific recording",
    labelnames=("site_name", "counter_name", "class_name"),
)
opendatacam_counter_total_items_counter = Counter(
    "opendatacam_counter_items",
    "Total number of counted items",
    labelnames=("site_name",),
)
