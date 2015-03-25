__author__ = 'katharine'

from peewee import *
import json
import logging
import uuid
import dateutil.parser
from dateutil.tz import tzlocal, tzutc
import datetime
import calendar
import struct

from layout import TimelineLayout

logger = logging.getLogger("pypkjs.timeline.model")
db = SqliteDatabase(None)


class BaseModel(Model):
    class Meta:
        database = db


class UTCDateTimeField(DateTimeField):
    def python_value(self, value):
        return dateutil.parser.parse(value)

    def db_value(self, value):
        assert isinstance(value, datetime.datetime)
        assert value.tzinfo is not None
        return value.astimezone(tzutc()).strftime("%Y-%m-%dT%H:%M:%SZ")


class JSONField(TextField):
    def python_value(self, value):
        return json.loads(value)

    def db_value(self, value):
        return json.dumps(value)


class TimelineItem(BaseModel):
    TYPES = (
        ('notification', 'notification'),
        ('pin', 'pin'),
        ('reminder', 'reminder'),
    )

    uuid = CharField(unique=True, primary_key=True)  # object UUID
    parent = CharField(index=True)  # UUID of the object's "parent"
    has_sent = BooleanField(default=False)
    rejected = BooleanField(default=False)
    source_kind = CharField()
    type = CharField(choices=TYPES)
    created = UTCDateTimeField()
    updated = UTCDateTimeField()
    deleted = BooleanField(default=False)
    start_time = UTCDateTimeField()
    duration = IntegerField()
    layout = JSONField()
    actions = JSONField(default=[])

    @classmethod
    def from_web_pin(cls, pin):
        source_kind, parent = pin['dataSource'].split(':')
        return cls(uuid=pin['guid'], parent=parent, source_kind=source_kind, type='pin',
                   created=dateutil.parser.parse(pin['createTime']).replace(microsecond=0),
                   updated=dateutil.parser.parse(pin['updateTime']).replace(microsecond=0),
                   start_time=dateutil.parser.parse(pin['time']).replace(microsecond=0),
                   duration=pin.get('duration', 0),
                   layout=pin['layout'],
                   actions=pin.get('actions', []))

    def make_reminders(self, web_reminders):
        reminders = []
        for reminder in web_reminders[:3]:
            at = dateutil.parser.parse(reminder['time'])
            if at > datetime.datetime.utcnow().replace(tzinfo=tzutc()):
                reminders.append(TimelineItem(uuid=str(uuid.uuid4()), parent=self.uuid, source_kind=self.source_kind,
                                    type='reminder', created=self.created, updated=self.updated, start_time=at,
                                    duration=0, layout=reminder['layout']))
        return reminders

    def get_notification_to_display(self, pin):
        prop = None
        timestamp = None
        # The logic here is kinda confusing. The idea is:
        # - The first time we send this pin, send the createMessage
        #   - So the first time we see it, if it has a createMessage, return that.
        #     - Unless it's over an hour old, in which case we... do nothing?
        #   - But if we've seen it before but not actually sent it, we might want to update the createMessage
        # - If we've both seen and actually sent the pin, then we may want to send the updateMessage.
        #   - If the updateMessage is 'newer' than the previous updateMessage, use that. This means either:
        #     - its updateMessageTimestamp is newer than before, or
        #     - it didn't previously have an updateMessage
        # If none of the above requirements are satisfied, do nothing.

        # First, dig up whatever we already have.
        old_notification_query = TimelineItem.select().where((TimelineItem.parent == self.uuid) & (TimelineItem.type == 'notification'))
        if old_notification_query.exists():
            old_notification = old_notification_query.get()
            logger.debug("we have an old notification. has_sent: %s, start_time: %s", old_notification.has_sent, old_notification.start_time)
            # If we've sent one before and we have an updateMessage in the new pin...
            if old_notification.has_sent and 'updateMessage' in pin:
                new_timestamp = dateutil.parser.parse(pin['updateMessage']['time'])
                logger.debug("There exists an updateMessage (ts: %s)", new_timestamp)
                # *and* the new notification is newer than the previous one, then we should use that.
                if new_timestamp > old_notification.start_time:
                    logger.debug("It has a newer timestamp")
                    prop = 'updateMessage'
                    timestamp = new_timestamp
            # If we don't have a new updateMessage to send
            if prop is None:
                logger.debug("No updateMessage.")
                # But our pin *has* updated more recently
                if self.updated > old_notification.updated \
                        and not old_notification.has_sent \
                        and pin.get('createMessage', None) is not None:
                    logger.debug("But we've updated more recently and haven't yet sent the old notification; use createMessage")
                    # Then we probably want to get a new createMessage
                    prop = 'createMessage'
                    try:
                        timestamp = dateutil.parser.parse(pin['updateMessage']['time'])
                    except KeyError:
                        timestamp = dateutil.parser.parse(pin['createTime'])
        else:
            logger.debug("We have no existing notifications; make a new one from createMessage")
            # If we don't have anything from before, use the createMessage, if any.
            if pin.get('createMessage', None) is not None:
                prop = 'createMessage'
                try:
                    timestamp = dateutil.parser.parse(pin['updateMessage']['time'])
                except KeyError:
                    timestamp = dateutil.parser.parse(pin['createTime'])
        if prop is not None:
            logger.debug("Notification!")
            return TimelineItem(uuid=str(uuid.uuid4()), parent=self.uuid, source_kind=self.source_kind,
                                type='notification', created=self.created, updated=self.updated, start_time=timestamp,
                                duration=0, layout=pin[prop]['layout'])
        else:
            logger.debug("No notification")
            return None

    def exists(self):
        return TimelineItem.select().where(TimelineItem.uuid == self.uuid).exists()

    @property
    def children(self):
        return list(TimelineItem.select().where(TimelineItem.parent == self.uuid))

    @property
    def parent_item(self):
        try:
            return TimelineItem.select().where(TimelineItem.uuid == self.parent).get()
        except TimelineItem.DoesNotExist:
            return None

    def serialise(self, fw_mapping):
        type_map = {
            'notification': 1,
            'pin': 2,
            'reminder': 3,
        }
        layout = TimelineLayout(self, fw_mapping)
        attribute_count, serialised_layout = layout.serialise()
        actions = TimelineActionSet(self)
        action_count, serialised_actions = actions.serialise()
        payload = serialised_layout + serialised_actions
        return struct.pack(
            "<16s16sIHBBBBHBB",
            uuid.UUID(self.uuid).bytes,                                 # uuid
            uuid.UUID(self.parent).bytes,                               # parent
            calendar.timegm(self.start_time.utctimetuple()),            # timestamp
            self.duration,                                              # duration
            type_map[self.type],                                        # type
            0,                                                          # flags
            0,                                                          # status
            layout.layout_id,                                           # layout
            len(payload),                                               # payload_length
            attribute_count,                                            # num_attributes
            action_count,                                               # num_actions
        ) + payload

    def get_complete_layout(self):
        parent = self.parent_item
        if parent is not None:
            final_layout = parent.layout.copy()
        else:
            final_layout = {}
        final_layout.update(self.layout)
        return final_layout

    def update_topics(self, topics):
        with db.atomic():
            PinTopic.delete().where(PinTopic.pin == self.uuid).execute()
            for topic in topics:
                if TimelineSubscription.select().where(TimelineSubscription.topic == topic).exists():
                    pin_topic = PinTopic(pin=self, topic=topic)
                    pin_topic.save(force_insert=True)


class TimelineState(BaseModel):
    key = CharField(unique=True, primary_key=True)
    value = CharField()

    @classmethod
    def get(cls, key, default=None):
        try:
            return cls.select().where(cls.key == key).get().value
        except cls.DoesNotExist:
            return default

    @classmethod
    def set(cls, key, value):
        cls.insert(key=key, value=value).upsert().execute()


class TimelineSubscription(BaseModel):
    topic = CharField(primary_key=True)

    @classmethod
    def subscribe(cls, topic):
        try:
            sub = cls(topic=topic)
            sub.save(force_insert=True)
        except IntegrityError:
            pass

    @classmethod
    def unsubscribe(cls, topic):
        cls.delete().where(cls.topic == topic).execute()


class PinTopic(BaseModel):
    pin = ForeignKeyField(TimelineItem, index=True, on_delete="CASCADE")
    topic = ForeignKeyField(TimelineSubscription, index=True, on_delete="CASCADE")

    @classmethod
    def pins_with_only(cls, topic):
        cursor = db.execute_sql("""
        SELECT pin_id
        FROM pintopic AS t1
        WHERE
          t1.topic_id = ?
          AND (SELECT
               COUNT(DISTINCT topic_id)
               FROM pintopic AS t2
               WHERE t1.pin_id = t2.pin_id) = 1""", (topic,))
        return [x[0] for x in cursor]

    class Meta:
        primary_key = CompositeKey('pin', 'topic')


class TimelineActionSet(object):
    DEFAULT_ACTIONS = {
        'pin': ((), ({'type': 'remove', 'title': 'Remove'}, {'type': 'mute', 'title': 'Mute App'})),
        'reminder': (({'type': 'dismiss', 'title': 'Dismiss'},), ({'type': 'openPin', 'title': 'More'}, {'type': 'mute', 'title': 'Mute App'})),
        'notification': (({'type': 'dismiss', 'title': 'Dismiss'},), ({'type': 'openPin', 'title': 'More'}, {'type': 'mute', 'title': 'Mute App'})),
    }
    ACTION_TYPES = {
        'dismiss': 0x4,
        'openWatchApp': 0x7,
        'remove': 0x9,
        'openPin': 0xa,
        'mute': 0x2,  # 0x02 = generic, which serves the purpose for us.
    }

    def __init__(self, pin):
        self.pin = pin

    def get_actions(self):
        return self.DEFAULT_ACTIONS[self.pin.type][0] + tuple(self.pin.actions) + self.DEFAULT_ACTIONS[self.pin.type][1]

    def serialise(self):
        action_count = 0
        serialised = ''
        for action_id, action in enumerate(self.get_actions()):
            action_type = self.ACTION_TYPES[action['type']]

            attribute_count, serialised_attributes = self.serialise_attributes(action)
            serialised_action = struct.pack('<BBB', action_id, action_type, attribute_count) + serialised_attributes
            action_count += 1
            logger.debug("serialised action. %d encoded: %s", attribute_count, serialised_action.encode('hex'))
            serialised += serialised_action

        return action_count, serialised

    def serialise_attributes(self, attributes):
        serialised = ''
        attribute_count = 0
        for key, value in attributes.iteritems():
            # Lazy approach for now; there are only two attributes, and they're completely different.
            if key == 'title':
                serialised += struct.pack("<BH%ds" % len(value), 0x01, len(value), value.encode('utf-8'))
                attribute_count += 1
            elif key == 'launchCode':
                serialised += struct.pack("<BHI", 0x0d, 4, value)
                attribute_count += 1

        return attribute_count, serialised


def prepare_db(filename):
    db.init(filename)
    db.connect()
    db.execute_sql("PRAGMA foreign_keys=ON")
    db.create_tables([TimelineItem, TimelineState, TimelineSubscription, PinTopic], True)
