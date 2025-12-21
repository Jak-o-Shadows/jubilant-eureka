import functools
import typing


# A unique object to act as a sentinel for uncached values.
# This is more robust than using `None` as a sentinel, as `None` could be a valid cached value.
_sentinel = object()

class cached_property:
    """
    A decorator that converts a method into a cached property.
    
    The property's value is computed by the decorated getter method on first access.
    Subsequent accesses return the cached value. The cache is automatically
    invalidated when the property's setter is called.
    
    Usage:
        class MyClass:
            @cached_property
            def my_prop(self):
                # Expensive computation
                return 42
    
            @my_prop.setter
            def my_prop(self, value):
                # Set some internal state
                self._my_prop = value
    """
    
    def __init__(self, fget):
        self.fget = fget
        self.fset = None
        self.cache_attr_name = f'_cached_{fget.__name__}'
        functools.update_wrapper(self, fget)
        
    def __get__(self, instance, owner):
        if instance is None:
            return self
        
        cached_value = getattr(instance, self.cache_attr_name, _sentinel)
        if cached_value is not _sentinel:
            return cached_value
        
        value = self.fget(instance)
        setattr(instance, self.cache_attr_name, value)
        return value
    
    def __set__(self, instance, value):
        if self.fset is None:
            raise AttributeError(f"can't set attribute '{self.fget.__name__}'")
        
        self.fset(instance, value)
        # Invalidate the cache by deleting the cached attribute if it exists.
        if hasattr(instance, self.cache_attr_name):
            delattr(instance, self.cache_attr_name)
            
    def setter(self, fset):
        """Decorator to define the property's setter."""
        self.fset = fset
        return self
